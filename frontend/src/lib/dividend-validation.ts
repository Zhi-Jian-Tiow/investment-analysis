// Mirrors backend/app/portfolio/schemas.py's VR-008/009/010/011 validators
// exactly, so inline errors show before a round-trip to the server.

export function validatePerShareAmount(value: string): string | null {
  if (!value.trim()) return "Dividend per share is required";
  if (!/^\d+(\.\d{1,6})?$/.test(value.trim())) {
    return "Dividend per share can have at most 6 decimal places";
  }
  if (parseFloat(value) <= 0) return "Dividend per share must be greater than zero";
  return null;
}

export function validateQualifyingShares(value: string, positionTotalShares: number): string | null {
  if (!value.trim()) return "Qualifying shares is required";
  if (!/^\d+$/.test(value.trim())) return "Qualifying shares must be a whole number";
  const n = parseInt(value, 10);
  if (n < 1) return "Qualifying shares must be at least 1";
  if (n > positionTotalShares) {
    return `Qualifying shares cannot exceed the position's current total shares (${positionTotalShares.toLocaleString("en-MY")})`;
  }
  return null;
}

export function validateDividendPaymentDate(value: string): string | null {
  if (!value) return "Payment date is required";
  const maxDate = new Date();
  maxDate.setDate(maxDate.getDate() + 30);
  maxDate.setHours(23, 59, 59, 999);
  if (new Date(value) > maxDate) return "Payment date cannot be more than 30 days in the future";
  return null;
}

export function validateExDividendDate(value: string, paymentDate: string): string | null {
  if (!value) return null;
  if (paymentDate && new Date(value) > new Date(paymentDate)) {
    return "Ex-dividend date must be before or on the payment date";
  }
  return null;
}
