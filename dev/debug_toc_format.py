import fitz, re

doc = fitz.open(r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.pdf")

# Just look at pages 1-5 to find TOC pattern (don't scan all 1200)
for i in range(min(5, len(doc))):
    text = doc[i].get_text()
    if 'Table of Contents' in text or 'CONTENTS' in text.upper():
        print(f"Page {i+1}: Found TOC header")
        # Show first 3000 chars
        print(text[:3000])
        print("\n--- Trying split patterns ---")
        patterns = [
            r"\n(?=\d+\.\s)",
            r"\n(?=[IVX]+\.\s)",
            r"\n\n(?=\d+\.)",
        ]
        for pat in patterns:
            parts = re.split(pat, text)
            non_empty = [p.strip() for p in parts if p.strip()]
            print(f"\nPattern: {repr(pat)} → {len(non_empty)} chunks")
            if non_empty:
                print(f"  First: {repr(non_empty[0][:100])}")
        break
else:
    print("No TOC header in first 5 pages")
    # Show page 1 text
    print("Page 1 preview:", doc[0].get_text()[:500])
