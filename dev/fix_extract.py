"""Fix the process_no_toc function properly"""
page_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\libs\pageindex_agent\pageindex_agent\page_index.py"
with open(page_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Restore the original extend line (was broken by previous fix)
# Replace the broken block with the correct structure
broken_block = """    toc_with_page_number = generate_toc_init(group_texts[0], model)
    for group_text in group_texts[1:]:
        toc_with_page_number_additional = generate_toc_continue(toc_with_page_number, group_text, model)
        # Ensure list type
if isinstance(toc_with_page_number, dict):
    toc_with_page_number = [toc_with_page_number]
if isinstance(toc_with_page_number_additional, list):
    toc_with_page_number.extend(toc_with_page_number_additional)
elif isinstance(toc_with_page_number_additional, dict):
    toc_with_page_number.append(toc_with_page_number_additional)

    logger.info(f"generate_toc: {toc_with_page_number}")
    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    logger.info(f"convert_physical_index_to_int: {toc_with_page_number}")

    return toc_with_page_number"""

fixed_block = """    toc_with_page_number = generate_toc_init(group_texts[0], model)
    # Ensure list type for initial result
    if isinstance(toc_with_page_number, dict):
        toc_with_page_number = [toc_with_page_number]
    for group_text in group_texts[1:]:
        toc_with_page_number_additional = generate_toc_continue(toc_with_page_number, group_text, model)
        if isinstance(toc_with_page_number_additional, list):
            toc_with_page_number.extend(toc_with_page_number_additional)
        elif isinstance(toc_with_page_number_additional, dict):
            toc_with_page_number.append(toc_with_page_number_additional)

    logger.info(f"generate_toc: {toc_with_page_number}")
    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    logger.info(f"convert_physical_index_to_int: {toc_with_page_number}")

    return toc_with_page_number"""

content = content.replace(broken_block, fixed_block)

# Fix 2: Fix generate_toc_init return to ensure list
content = content.replace(
    'return result if result else []',
    'return [result] if isinstance(result, dict) else (result if isinstance(result, list) else [])'
)

with open(page_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed page_index.py")
