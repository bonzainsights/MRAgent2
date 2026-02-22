import os
import sys

# temporarily change NVIDIA_LLAMA3_3_70B_INSTRUCT to a fake key to simulate failure
# actually, LLMProvider will use the key in settings, which is already loaded. 
# We can just change the key in the client dict or mock it.
# Another way is to just call the API with a bad model id? Actually if the model fails (e.g., rate limit or bad key), it should fallback.

from config.settings import NVIDIA_KEYS
# overwrite with bad key
NVIDIA_KEYS["llama_33_70b"] = "bad_key"

from providers.nvidia_llm import NvidiaLLMProvider

def test_fallback():
    provider = NvidiaLLMProvider()
    print("Testing fallback chain...")
    try:
        # It should try llama-3.3-70b (fail due to bad key), then kimi-k2.5 (fail if no key or works if key exists), 
        # then qwen3-coder, then llama-3.1-8b
        res = provider.chat([{"role": "user", "content": "Say 'hello fallback'"}], model="llama-3.3-70b", stream=False)
        print("Response received:", res["content"])
        print("Model used:", res["model"])
        if "meta/llama-3.3-70b-instruct" not in res["model"]:
            print("Fallback successful! Used:", res["model"])
        else:
            print("Did not fallback, used 70b anyway??")
    except Exception as e:
        print("All models in chain failed:", e)

if __name__ == "__main__":
    test_fallback()
