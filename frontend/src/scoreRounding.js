// Composite inputs are decimal scores/weights. Round their weighted sum once,
// half up, without binary floating-point errors at half-cent boundaries.
const decimalParts = (value) => {
  const [mantissa, exponent = "0"] = String(value).toLowerCase().split("e");
  const [whole, fraction = ""] = mantissa.split(".");
  const coefficient = BigInt(whole + fraction);
  const scale = fraction.length - Number(exponent);
  return scale >= 0
    ? [coefficient, scale]
    : [coefficient * 10n ** BigInt(-scale), 0];
};

export function compositePoints(available, normalizedWeights) {
  if (!available.length) return null;
  const products = available.map(([key, value]) => {
    const [score, scoreScale] = decimalParts(Number(value));
    const [weight, weightScale] = decimalParts(normalizedWeights[key]);
    return [score * weight, scoreScale + weightScale];
  });
  const scale = Math.max(...products.map(([, places]) => places));
  const denominator = 10n ** BigInt(scale);
  const sum = products.reduce((total, [coefficient, places]) => total + coefficient * 10n ** BigInt(scale - places), 0n);
  const magnitude = sum < 0n ? -sum : sum;
  // Dividing weighted points by 100 and converting to cents cancel out.
  const cents = (magnitude * 2n + denominator) / (denominator * 2n);
  return Number(sum < 0n ? -cents : cents) / 100;
}
