with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read().decode("utf-8", errors="replace")

# Fix double \r issue
content = content.replace("\r\r\n", "\r\n")

# Fix 1: change 'for title, text in matched:' to 'for node in matched:' and update body
old_loop_block = """    for title, text in matched:\r
        if title not in seen and len(text) > 200:\r
            seen.add(title)\r
            snippet = text[:5000]\r
            context_blocks.append("[" + title + "]\r
" + snippet)\r
            sources.append({"title": title, "page_range": "", "text": snippet[:500]})\r"""

new_loop_block = """    for node in matched:\r
        title = node.get("title", "")\r
        text = node.get("text", "")\r
        if title not in seen and len(text) > 200:\r
            seen.add(title)\r
            snippet = text[:5000]\r
            context_blocks.append("[" + title + "]\r
" + snippet)\r
            sources.append({"title": title, "page_range": "", "text": snippet[:500]})\r"""

if old_loop_block in content:
    content = content.replace(old_loop_block, new_loop_block)
    print("Fix 1 done: for-loop updated")
else:
    print("WARNING: could not find old_loop_block")
    # Show what we have
    idx = content.find("for title, text in matched")
    if idx >= 0:
        print("Found at:", repr(content[idx:idx+200]))

# Fix 2: kw_matches sort uses kw_key which is not defined in new code - use query_keywords
old_kw_sort = "kw_key.lower().split()"
new_kw_sort = "query_keywords"
if old_kw_sort in content:
    count = content.count(old_kw_sort)
    content = content.replace(old_kw_sort, new_kw_sort)
    print(f"Fix 2 done: replaced {count} occurrence(s) of kw_key.lower().split()")
else:
    print("WARNING: kw_key.lower().split() not found")

# Fix 3: remove the now-unused 'kw_key = " ".join(query_keywords)' line since it's no longer needed
# Actually, query_keywords is still needed for kw_search, so keep it

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)

print("Done writing")
