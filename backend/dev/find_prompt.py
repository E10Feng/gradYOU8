with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Find the prompt = f line
idx = content.find(b"prompt = f")
print("prompt = f at byte:", idx)

# Find the triple quotes
tq = content.find(b'f"""', idx)
print("f triple quote at:", tq)

# The prompt starts at the f"""
# Find the end of the prompt (the closing """)
# Start searching after the opening """
prompt_start = tq + 4  # skip f"""

# Find the closing """ but need to be careful about it being on its own line
# Search for """)  which would be the end of the f-string
# Look for the pattern: newline + 4+ spaces + closing quotes
search_from = prompt_start
for i in range(10):  # search up to 10 times
    next_tq = content.find(b'"""', search_from)
    if next_tq < 0:
        break
    # Check if the character before the triple quote is a quote
    char_before = content[next_tq - 1:next_tq]
    print(f"Triple quote #{i+1} at {next_tq}, char before: {repr(char_before)}")
    search_from = next_tq + 3

# Just get a big chunk and write to file
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\dev\prompt_chunk.bin", "wb") as f:
    f.write(content[tq:tq+3000])
print("Written")
