Create checkout.py at the repository root with these functions, and tests for them. Money values, in and out, are
decimal.Decimal; every money result is quantized to 0.01 with ROUND_HALF_UP.
1. price_after_discount(total, pct): the amount the customer pays after a pct % discount (not the discount itself).
   pct is a number from 0 to 100 inclusive; anything else raises ValueError.
2. shipping(subtotal, weight_kg): 0.00 when subtotal is at least 50.00. Otherwise 4.99 for the first kg plus 1.50 for each
   started kg beyond it (1 kg -> 4.99, 2.1 kg -> 7.99). weight_kg must be greater than 0, else ValueError.
3. loyalty_points(paid): one point per whole 10.00 of paid, as an int (39.99 -> 3); 0 for amounts below 10.00, never negative.
   The caller passes the price after discount, without shipping.
4. split_payment(total, n): n money amounts that add up exactly to total; the cents left over go to the first parts
   (10.00 split 3 ways -> [3.34, 3.33, 3.33]). n must be at least 1, else ValueError.
5. parse_coupon(code): "SAVE" followed by a whole number from 1 to 50 without leading zeros -> that number as an int.
   Case-insensitive, surrounding whitespace allowed ("  save10 " -> 10). Anything else -> None; it never raises.
