def normalize_phone(phone: str | None) -> str:
	"""Comparable form of a Tanzanian phone number: digits only, 255 country code.

	0712 345 678, +255712345678 and 255712345678 all become 255712345678, so
	the same person entered differently in Guests and Contributors matches.
	"""
	digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
	if digits.startswith("0") and len(digits) == 10:
		digits = "255" + digits[1:]
	elif len(digits) == 9 and digits[0] in "67":
		digits = "255" + digits
	return digits
