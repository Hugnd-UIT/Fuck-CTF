import os
import requests
import urllib.parse
import cli.rag as rag_ui

def search_github(word: str, model: str = None) -> dict:
    
    # Setup request
    headers = {
        "Authorization": f"token {os.environ['GITHUB_API_KEY']}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Setup target
    word = urllib.parse.quote(word[:200])
    url = f"https://api.github.com/search/issues?q={word}+is:issue"

    try:
        # Fetch issues
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Parse items
        items = data.get("items", [])[:10]
        results = []

        # Iterate items
        for item in items:
            title = item.get("title", "")
            body = item.get("body") or ""

            try:
                # Import agent
                from agent.pentest import PentestAgent
                import json

                # Initialize scorer
                scorer = PentestAgent(
                    model=model,
                    temperature=0.1,
                    tokens=50
                )

                # Build prompt
                prompt = f'''
                You are a security analyst evaluating a GitHub issue related to {word}.
                Score the relevance of this issue from 0 to 100.
                Only issues containing actual proof of concepts, logs, or technical analysis should get > 70.
                Spam or useless issues should get < 30.

                Issue Title: {title}
                Issue Body: {body[:2000]}

                Respond in JSON format: {{"score": 100}}
                '''

                # Build messages
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

                # Execute scoring
                text, _, _ = scorer.call(messages)

                try:
                    # Parse score
                    if "```json" in text:
                        json_str = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        json_str = text.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = text.strip()

                    res = json.loads(json_str)
                    score = res.get("score", 0)
                except:
                    # Handle error
                    score = 0

                # Check threshold
                if isinstance(score, (int, float)) and score < 70:
                    continue

                # Append result
                results.append({
                    "title": title,
                    "url": item.get("html_url"),
                    "state": item.get("state"),
                    "body": body
                })
                rag_ui.issue(item.get('html_url'))

            # Handle item error
            except Exception as e:
                rag_ui.fail('Github error', e)
                pass

            # Check limit
            if len(results) >= 5:
                break

        # Return results
        return {"github_issues": results}

    # Handle global error
    except Exception as err:
        rag_ui.fail('Github search', err)
        return {"error": str(err)}