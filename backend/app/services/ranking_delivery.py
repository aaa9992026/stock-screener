"""Bound ranking builds independently of HTTP traffic; serve complete snapshots."""
import hashlib
import json
import logging
import threading
import time
from functools import wraps
from collections import OrderedDict
from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError

from app.models import RankingResponse

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
VERSION = "ranking-delivery-v2-stored-prices"
FRESH_SECONDS = 120
MAX_AGE_SECONDS = 900
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024


def trace_stage(name):
    def decorate(function):
        @wraps(function)
        def traced(*args, **kwargs):
            started = time.monotonic()
            try:
                return function(*args, **kwargs)
            except Exception as error:
                logger.error('ranking_stage_failed stage=%s error_type=%s', name, type(error).__name__)
                raise
            finally:
                logger.info('ranking_stage stage=%s duration_ms=%d rss_kib=%s',
                            name, (time.monotonic()-started)*1000, memory_kib())
        return traced
    return decorate


def memory_kib():
    """Linux resident memory only; no environment, process command or secrets."""
    try:
        with open('/proc/self/status', encoding='ascii') as source:
            for line in source:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None


class RankingDelivery:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = OrderedDict()
        self.active = set()
        self.cache = OrderedDict()
        self.retry_after = {}
        self.running = False

    def _remember(self, identity, value):
        with self.lock:
            self.cache[identity] = value
            self.cache.move_to_end(identity)
            while len(self.cache) > 8:
                self.cache.popitem(last=False)

    def _schedule(self, identity, args, factory, builder):
        with self.lock:
            if identity in self.active or identity in self.pending:
                return
            if time.monotonic() < self.retry_after.get(identity, 0) or len(self.pending) >= 8:
                return
            self.pending[identity] = (args, factory, builder)
            if not self.running:
                self.running = True
                threading.Thread(target=self._run, name='ranking-snapshot-build', daemon=True).start()

    def _run(self):
        while True:
            with self.lock:
                if not self.pending:
                    self.running = False
                    return
                identity, (args, factory, builder) = self.pending.popitem(last=False)
                self.active.add(identity)
            started = time.monotonic()
            db = None
            try:
                db = factory()
                payload = builder(db=db, **args)
                serializing = time.monotonic()
                encoded = json.dumps(payload, separators=(',', ':'), allow_nan=False)
                size = len(encoded.encode('utf-8'))
                logger.info('ranking_serialization market=%s duration_ms=%d bytes=%d',
                            args['market'], (time.monotonic()-serializing)*1000, size)
                if size > MAX_PAYLOAD_BYTES:
                    logger.error('ranking_response_oversize market=%s bytes=%d', args['market'], size)
                    raise ValueError('ranking response limit')
                stamp = datetime.utcnow()
                saved = db.get(RankingResponse, args['market'])
                if saved is None:
                    saved = RankingResponse(market=args['market'])
                    db.add(saved)
                saved.request_key, saved.payload_json, saved.updated_at = identity[1], encoded, stamp
                db.commit()
                self._remember(identity, (stamp, encoded))
                logger.info('ranking_build market=%s duration_ms=%d rows=%d bytes=%d rss_kib=%s',
                            args['market'], (time.monotonic()-started)*1000,
                            len(payload.get('rows', [])), size, memory_kib())
            except Exception as error:
                if db is not None:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                # Never log SQL, bound parameters, provider URLs or exception text.
                logger.error('ranking_build_failed market=%s duration_ms=%d error_type=%s rss_kib=%s',
                             args['market'], (time.monotonic()-started)*1000,
                             type(error).__name__, memory_kib())
                with self.lock:
                    self.retry_after[identity] = time.monotonic() + 30
                    while len(self.retry_after) > 16:
                        self.retry_after.pop(next(iter(self.retry_after)))
            finally:
                if db is not None:
                    try:
                        db.close()
                    except Exception:
                        pass
                with self.lock:
                    self.active.discard(identity)

    def serve(self, db, args, factory, builder):
        started = time.monotonic()
        key = hashlib.sha256(json.dumps([VERSION, args], sort_keys=True).encode()).hexdigest()
        identity = (id(db.get_bind()), key)
        with self.lock:
            cached = self.cache.get(identity)
        if cached is None:
            try:
                saved = db.get(RankingResponse, args['market'])
                if saved is not None and saved.request_key == key:
                    cached = (saved.updated_at, saved.payload_json)
                    self._remember(identity, cached)
            except SQLAlchemyError as error:
                try:
                    db.rollback()
                except Exception:
                    pass
                logger.error('ranking_cache_read_failed market=%s error_type=%s', args['market'], type(error).__name__)
                raise HTTPException(503, 'Ranking snapshot storage is temporarily unavailable.', headers={'Retry-After': '5'}) from None
        age = max(0, (datetime.utcnow()-cached[0]).total_seconds()) if cached else MAX_AGE_SECONDS+1
        if age >= FRESH_SECONDS:
            self._schedule(identity, dict(args), factory, builder)
        if cached is None or age > MAX_AGE_SECONDS:
            logger.info('ranking_request market=%s state=warming duration_ms=%d', args['market'], (time.monotonic()-started)*1000)
            raise HTTPException(503, detail={'code': 'RANKING_WARMING', 'message': 'Ranking snapshot is warming; retry shortly.'}, headers={'Retry-After': '5'})
        state = 'fresh' if age < FRESH_SECONDS else 'stale'
        logger.info('ranking_request market=%s state=%s age_seconds=%d duration_ms=%d', args['market'], state, age, (time.monotonic()-started)*1000)
        return Response(cached[1], media_type='application/json', headers={
            'Cache-Control': 'no-store', 'X-Ranking-Cache': state, 'Age': str(int(age)),
        })


delivery = RankingDelivery()
