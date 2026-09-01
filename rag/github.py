import os
import requests
import urllib.parse
import cli.rag as rag_ui

# Search GitHub issues
def search_github(word: str) -> dict:
    headers = {
        "Authorization": f"token {os.environ['GITHUB_API_KEY']}",
        "Accept": "application/vnd.github.v3+json"
    }

    word = urllib.parse.quote(word[:200])
    url = f"https://api.github.com/search/issues?q={word}+is:issue"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])[:10]
        results = []

        for item in items:
            title = item.get("title", "")
            body = item.get("body") or ""

            try:
                from agent.pentest import PentestAgent
                import json

                # Initialize issue scorer
                scorer = PentestAgent(
                    model=os.getenv("MODEL", "deepseek/deepseek-v4-flash"),
                    temperature=0.1,
                    tokens=50
                )

                # Build scoring prompt
                prompt = f'''
                You are a security analyst evaluating a GitHub issue related to {word}.
                Score the relevance of this issue from 0 to 100.
                Only issues containing actual proof of concepts, logs, or technical analysis should get > 70.
                Spam or useless issues should get < 30.

                Issue Title: {title}
                Issue Body: {body[:2000]}

                Respond in JSON format: {{"score": 100}}
                '''

                messages = [
                    {
                        "role": "system",
                        "content": "You are a JSON-only scoring bot. Output ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

                # Score issue relevance
                text, _, _ = scorer.call(messages)

                try:
                    # Parse scoring response
                    if "```json" in text:
                        json_str = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        json_str = text.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = text.strip()

                    res = json.loads(json_str)
                    score = res.get("score", 0)
                except:
                    score = 0

                if isinstance(score, (int, float)) and score < 70:
                    continue

                results.append({
                    "title": title,
                    "url": item.get("html_url"),
                    "state": item.get("state"),
                    "body": body
                })
                rag_ui.gh(item.get('html_url'))

            except Exception as e:
                rag_ui.gherr(e)
                pass

            if len(results) >= 5:
                break

        return {"github_issues": results}

    except Exception as err:
        rag_ui.ghserr(err)
        return {"error": str(err)}