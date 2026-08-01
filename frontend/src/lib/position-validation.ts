// Mirrors backend/app/portfolio/schemas.py's VR-004/005/006 validators
// exactly, so inline errors show before a round-trip to the server.

export function validateStockCode(value: string): string | null {
  if (!value.trim()) return "Stock code is required";
  return null;
}

export function validateStockName(value: string): string | null {
  if (!value.trim()) return "Stock name is required";
  if (value.length > 100) return "Stock name must be under 100 characters";
  return null;
}

export function validateShares(value: string): string | null {
  if (!value.trim()) return "Number of shares is required";
  if (!/^\d+$/.test(value.trim())) return "Number of shares must be a whole number";
  const n = parseInt(value, 10);
  if (n < 1) return "Number of shares must be greater than zero";
  if (n > 99_999_999) return "Number of shares cannot exceed 99,999,999";
  return null;
}

export function validatePurchasePrice(value: string): string | null {
  if (!value.trim()) return "Purchase price is required";
  if (!/^\d+(\.\d{1,4})?$/.test(value.trim())) {
    return "Purchase price can have at most 4 decimal places";
  }
  if (parseFloat(value) <= 0) return "Purchase price must be greater than zero";
  return null;
}

export function validatePurchaseDate(value: string): string | null {
  if (!value) return "Purchase date is required";
  const today = new Date();
  today.setHours(23, 59, 59, 999);
  if (new Date(value) > today) return "Purchase date cannot be in the future";
  return null;
}

export function validateBrokerId(value: string): string | null {
  if (!value) return "Please select a broker";
  return null;
}
