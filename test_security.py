from agents.core import AgentCore
import json

agent = AgentCore()
print("Initialized agent.")

# Let's directly call _execute_tool_calls to test the is_safe_command logic
assistant_msg = {"content": "Executing command"}

# Test 1: Safe command (ls)
tool_calls_safe = [{
    "id": "tc_safe1",
    "type": "function",
    "function": {
        "name": "execute_terminal",
        "arguments": json.dumps({"command": "ls -la"})
    }
}]

# Mock approval callback to just print
def mock_approval(desc):
    print(desc)
    return False

agent.approval_callback = mock_approval

print("Testing safe command (should execute without prompt):")
agent._execute_tool_calls(tool_calls_safe, assistant_msg)
print("Safe command done.\n")

# Test 2: Unsafe command (rm)
tool_calls_unsafe = [{
    "id": "tc_unsafe1",
    "type": "function",
    "function": {
        "name": "execute_terminal",
        "arguments": json.dumps({"command": "rm -rf /tmp/foo"})
    }
}]
print("Testing unsafe command (should trigger prompt and reject):")
agent._execute_tool_calls(tool_calls_unsafe, assistant_msg)
print("Unsafe command done.\n")

# Test 3: Unsafe chaining
tool_calls_chain = [{
    "id": "tc_unsafe2",
    "type": "function",
    "function": {
        "name": "execute_terminal",
        "arguments": json.dumps({"command": "ls && rm -rf /"})
    }
}]
print("Testing chained command (should trigger prompt and reject):")
agent._execute_tool_calls(tool_calls_chain, assistant_msg)
print("Chained command done.\n")

