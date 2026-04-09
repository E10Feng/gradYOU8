"""Fix all MiniMax issues in libs/utils.py and libs/page_index.py"""

# Fix utils.py - extract_json
utils_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\libs\pageindex_agent\pageindex_agent\utils.py"
with open(utils_path, "r", encoding="utf-8") as f:
    utils_content = f.read()

old_extract = '''def extract_json(content: str) -> dict | list:
    try:
        start_idx = content.find("```json")
        if start_idx != -1:
            start_idx += 7
            end_idx = content.rfind("```")
            json_content = content[start_idx:end_idx].strip()
        else:
            json_content = content.strip()
        json_content = json_content.replace("None", "null").replace("\\n", " ").replace("\\r", " ")
        json_content = " ".join(json_content.split())
        return json.loads(json_content)
    except json.JSONDecodeError:
        try:
            return json.loads(json_content.replace(",]", "]").replace(",}", "}"))
        except Exception:
            logger.error("Failed to parse JSON")
            return {}
    except Exception as e:
        logger.error("Unexpected error extracting JSON: %s", e)
        return {}'''

new_extract = '''def extract_json(content: str) -> dict | list:
    """Extract JSON from MiniMax response - handles thinking tags and post-thinking JSON."""
    try:
        start_idx = content.find("```json")
        if start_idx != -1:
            start_idx += 7
            end_idx = content.rfind("```")
            json_content = content[start_idx:end_idx].strip()
        else:
            json_content = content.strip()
        # Strip thinking tags (Minimax <thinking>...</thinking>)
        json_content = re.sub(r"<think>.*?</think>", "", json_content, flags=re.DOTALL)
        json_content = re.sub(r"<start_index_\\d+>.*?<end_index_\\d+>", "", json_content, flags=re.DOTALL)
        # Also check for JSON appearing AFTER thinking ends
        last_toc = json_content.rfind("</think>")
        post_thinking = ""
        if last_toc != -1:
            post_thinking = json_content[last_toc + len("</think>"):].strip()
        # Find the first '{' and last '}' as JSON boundaries
        first_brace = json_content.find("{")
        last_brace = json_content.rfind("}")
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            json_content = json_content[first_brace:last_brace + 1]
        json_content = json_content.replace("None", "null").replace("\\n", " ").replace("\\r", " ")
        json_content = " ".join(json_content.split())
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            pass
        # Handle multiple JSON objects without array wrapper
        try:
            stripped = json_content.strip()
            if stripped.startswith("{") and ",{" in stripped:
                json_content = "[" + json_content + "]"
                return json.loads(json_content)
        except Exception:
            pass
        # Try JSON after thinking ends
        if post_thinking:
            try:
                return json.loads(post_thinking)
            except json.JSONDecodeError:
                pass
            try:
                first_brace = post_thinking.find("{")
                last_brace = post_thinking.rfind("}")
                if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                    return json.loads(post_thinking[first_brace:last_brace + 1])
            except Exception:
                pass
        logger.error("Failed to parse JSON")
        return {}
    except Exception as e:
        logger.error("Unexpected error extracting JSON: %s", e)
        return {}'''

utils_content = utils_content.replace(old_extract, new_extract)

# Fix finish_reason in utils.py ChatGPT_API_with_finish_reason
utils_content = utils_content.replace(
    'if finish_reason == "finished":',
    'if finish_reason in ("finished", "stop", "length"):'
)
utils_content = utils_content.replace(
    'while not (if_complete == "yes" and finish_reason == "finished"):',
    'while not (if_complete == "yes" and finish_reason in ("finished", "stop", "length")):'
)

with open(utils_path, "w", encoding="utf-8") as f:
    f.write(utils_content)
print("Fixed utils.py")

# Fix page_index.py
page_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\libs\pageindex_agent\pageindex_agent\page_index.py"
with open(page_path, "r", encoding="utf-8") as f:
    page_content = f.read()

# Fix finish_reason == "finished" -> in ("finished", "stop", "length")
page_content = page_content.replace(
    'finish_reason == "finished"',
    'finish_reason in ("finished", "stop", "length")'
)

with open(page_path, "w", encoding="utf-8") as f:
    f.write(page_content)
print("Fixed page_index.py")
print("Done!")
