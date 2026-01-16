import asyncio
import json
import sys
from a2a.client import ClientFactory, ClientConfig, create_text_message_object
from a2a.types import Role

try:
    from a2a.utils import get_message_text
except ImportError:
    from a2a.utils.message import get_message_text

async def main():
    print(">>> Connecting to Green Agent...")
    try:
        # FIX: Set a generous timeout (300s = 5 mins) for the benchmark run
        # Note: 'request_timeout' might vary by SDK version, but usually helps.
        # We also rely on the server sending "keep-alive" messages.
        config = ClientConfig(polling=False) 
        # Monkey-patch default timeout if config doesn't expose it
        import httpx
        httpx.AsyncClient.__init__.__defaults__ = (None, None, None, httpx.Timeout(300.0),) 

        client = await ClientFactory(config).connect("http://localhost:8000")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    task_payload = json.dumps({
        "participants": {"planner": "http://purple-agent:8001"},
        "config": {"domain": "blocks", "index": 1}
    })

    print(f">>> Sending Task (Payload: {task_payload})")
    
    try:
        msg = create_text_message_object(role=Role.user, content=task_payload)
        
        async for response in client.send_message(msg):
            # Print responses as they stream in
            if hasattr(response, 'parts'): # It's a Message object
                print(f"Received update: {get_message_text(response)}")
            else:
                print(f"Received raw: {response}")
            
    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())