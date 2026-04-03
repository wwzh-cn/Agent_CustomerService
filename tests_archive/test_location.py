#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
import asyncio
from agent.tools.agent_tools import get_user_location

print("Calling get_user_location()")
result = get_user_location()
print(f"Result: {result}")