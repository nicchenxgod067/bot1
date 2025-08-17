import os
import json
import time
import requests
from github import Github
from itertools import islice

def chunked(iterable, size):

    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk

class TokenBatchProcessor:
    def __init__(self, github_token, repository_name, batch_size=100):
        if not github_token or not repository_name:
            raise ValueError("Missing GITHUB_TOKEN or GITHUB_REPOSITORY environment variable.")
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repository_name)
        self.session = requests.Session()
        self.batch_size = batch_size
       
        self.endpoint = "https://jw/terminalgen_jwt?bypass_cache=true"

    def load_input(self, region):
        path = f"input_{region}.json"
        contents = self.repo.get_contents(path)
        return json.loads(contents.decoded_content.decode())

    def save_output(self, region, tokens):
        output_file = f"token_{region}.json"
        content = json.dumps(tokens, indent=2)
        try:
            existing = self.repo.get_contents(output_file)
            self.repo.update_file(
                output_file,
                f"Update tokens for {region} (total={len(tokens)})",
                content,
                existing.sha
            )
        except Exception:
            self.repo.create_file(
                output_file,
                f"Create tokens for {region}",
                content
            )
        print(f"[+] Saved {len(tokens)} tokens to {output_file}")

    def fetch_batch(self, batch):
        
        payload = [{"uid": entry["uid"], "password": entry["password"]} for entry in batch]
        resp = self.session.post(self.endpoint, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def process_region(self, region):
        print(f"[=] Processing region: {region}")
        data = self.load_input(region)
        all_tokens = []
        failed_batches = []
        
        for idx, batch in enumerate(chunked(data, self.batch_size), start=1):
            print(f"   > Fetching batch {idx} (size={len(batch)})...")
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    results = self.fetch_batch(batch)
                   
                    batch_tokens = []
                    for item in results:
                        token_val = item.get("token")
                        if token_val:
                            batch_tokens.append({"token": token_val})
                    
                    all_tokens.extend(batch_tokens)
                    print(f"   ✓ Batch {idx} successful: {len(batch_tokens)} tokens")
                    
                    
                    self.save_output(region, all_tokens)
                    
                    time.sleep(3)
                    break  
                    
                except Exception as e:
                    retry_count += 1
                    print(f"[!] Batch {idx} failed (attempt {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        print(f"   → Retrying batch {idx} in 5 seconds...")
                        time.sleep(5)
                    else:
                        print(f"[!] Batch {idx} failed after {max_retries} attempts, skipping...")
                        failed_batches.append(idx)
                        time.sleep(3)
        
        print(f"[✓] Completed region: {region}")
        print(f"   → Total tokens generated: {len(all_tokens)}")
        print(f"   → Total input entries: {len(data)}")
        print(f"   → Failed batches: {len(failed_batches)}")
        if failed_batches:
            print(f"   → Failed batch indices: {failed_batches}")

if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    repository_name = os.getenv("GITHUB_REPOSITORY")
    processor = TokenBatchProcessor(github_token, repository_name, batch_size=100)
    processor.process_region("bd")
