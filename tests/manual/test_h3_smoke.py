# Test H3 index handling
test_indexes = [
    '892e42426ffffff',
    '872e42426ffffff',
]

for idx in test_indexes:
    # Check length (resolution 9 = 15 chars)
    valid_hex = all(c in '0123456789abcdefABCDEF' for c in idx)
    print(f'Index: {idx}, length: {len(idx)}, valid hex: {valid_hex}')

# Try to import h3 core functions only
try:
    import h3
    print("h3 imported successfully")
    # Test basic operations
    idx = h3.geo_to_h3(-7.1333, 109.2, 9)
    print(f"geo_to_h3 result: {idx}")
except Exception as e:
    print(f"h3 import error: {e}")
    # Fall back to string-based H3 handling
    print("Will use string-based H3 index handling")