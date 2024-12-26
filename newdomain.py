from aiohttp import web
from aiohttp.web import Request, Response, json_response
import random


routes = web.RouteTableDef()


# globals
hub_url = None
domain_id = None
domain_secret = None
item_ids = {}  
prizes = []
users = {}  # Map from user id to their state


domain_items = [
    {
        "name": "sales-flyer",
        "description": "A sparkly pink sales flyer for the boutique",
        "verb": {
            "read": 'The flyer reads <q>VIP Room Code: VIP123</q>'
        },
    },
    {
        "name": "gold-card",
        "description": "A gold VIP membership card that sparkles in the light.",
        "verb": {},
        "depth": 1
    },
    {
        "name": "lipbalm",  # Depth-0 item for other domains
        "description": "A limited edition mood-changing lipbalm in fancy packaging.",
        "verb": {
            "use": "You apply the lipbalm and feel fabulous!"
        },
        "depth": 0
    },
    {
        "name": "fashion-magazine",  # New no-depth item
        "description": "A glossy magazine showcasing the latest fashion trends.",
        "verb": {
            "read": "The magazine features articles about upcoming designer collections."
        },
    },
    {
        "name": "diamond-necklace",  # New depth-2 item
        "description": "An exquisite diamond necklace that catches the light beautifully.",
        "verb": {
            "wear": "You put on the necklace and feel bougie!"
        },
        "depth": 2
    }
]


class UserState:
    def __init__(self):
        self.location = 'boutique-entrance'  # Starting location
        self.keypad_locked = True  # For VIP room
        self.dressing_room_used = False  
        self.visited = set()
        self.has_departed = False  # Track if user has departed


locs = {
    'boutique-entrance': {
        'description': "You're in a glamorous boutique entrance with crystal chandeliers and marble floors. Shopping bags from various designers line the display windows. (Head north to shop, east to fitting rooms, south to journey)",
        'exits': {'north': 'shopping-area', 'east': 'fitting-rooms', 'south': 'journey'},
        'items': []
    },
    'shopping-area': {
    'description': "Racks of designer clothes surround you...",
    'exits': {'south': 'boutique-entrance', 'up': 'accessories', 'east': 'vip-lounge'},
    'items': [] 
    },
    'accessories': {
        'description': "Sparkling jewelry and designer handbags are displayed in illuminated glass cases. A makeup counter shimmers with the latest products. (Go down to return to shopping area)",
        'exits': {'down': 'shopping-area'},
        'items': []
    },
    'fitting-rooms': {
        'description': "Plush velvet curtains separate individual fitting rooms. A special VIP room with a gold door and keypad catches your eye. (Go west to return to entrance, then head north and east from there to reach the VIP lounge",
        'exits': {'west': 'boutique-entrance'},
        'items': []
    },
    'vip-lounge': {
        'description': "An exclusive area with a digital keypad by the door. Hint: check the sales-flyer for the code and 'tell keypad ____', then explore other domains to find a gold card ('use gold-card')! (West to shopping area → south to entrance/up to accessories)",
        'exits': {'west': 'shopping-area'},
        'items': []
    }
}




@routes.post('/depart')
async def handle_depart(req: Request) -> Response:
    data = await req.json()
   
    if data['secret'] != domain_secret:
        return Response(status=403)
       
    user_id = data['user']
    print(f"DEPART - Before departure: User {user_id} state exists: {user_id in users}")
    if user_id in users:
        print(f"DEPART - Keypad state: {users[user_id].keypad_locked}")
        users[user_id].has_departed = True  # Mark as departed instead of deleting
        print(f"DEPART - User marked as departed, keypad state: {users[user_id].keypad_locked}")
   
    return Response(status=200)


@routes.post('/newhub')
async def register_with_hub_server(req: Request) -> Response:
    global hub_url, domain_id, domain_secret
   
    hub_url = await req.text()
    # Only register once
    async with req.app.client.post(hub_url+'/register', json={
        'url': whoami,
        'name': "Exclusive Fashion Boutique",
        'description': "A luxurious shopping destination with designer items and a mysterious VIP room. Let's start our journey by exploring north and taking what you find then after that go upstairs before returning downstairs to continue shopping. (Check item IDs of the items you journey (lipbalm, gold-card, diamond-necklace) for by looking in your invetory after you get them )",
        'items': domain_items,
    }) as resp:
        data = await resp.json()
        if 'error' in data:
            return json_response(status=resp.status, data=data)
       
        domain_id = data['id']
        domain_secret = data['secret']
       
        # Clear and reinitialize state
        item_ids.clear()
        for i, item_id in enumerate(data['items']):
            item_ids[i] = item_id
        
        users.clear()
        for loc in locs.values():
            loc['items'] = []
           
        # Set initial items
        locs['boutique-entrance']['items'] = [{
            'name': 'sales-flyer',
            'id': item_ids[0],
            'description': domain_items[0]['description'],
            'verb': domain_items[0]['verb']
        }]
       
        return json_response({'ok': 'Exclusive Fashion Boutique registered successfully'})


@routes.post('/arrive')
async def register_with_hub_server(req: Request) -> Response:
    """Called by hub server each time a user enters or re-enters this domain."""
    global prizes
    data = await req.json()
    
    if data['secret'] != domain_secret:
        return Response(status=403)
        
    prizes = data.get('prize', [])
    user_id = data['user']
    arrival_direction = data.get('from', 'login')
    
    print(f"ARRIVE - Before: User {user_id} state exists: {user_id in users}")
    
    if user_id in users:
        print(f"ARRIVE - Current keypad state: {users[user_id].keypad_locked}")
        print(f"ARRIVE - Has departed: {users[user_id].has_departed}")
        users[user_id].has_departed = False
        users[user_id].location = 'boutique-entrance'
        print(f"ARRIVE - Preserved state with keypad: {users[user_id].keypad_locked}")
    else:
        print(f"ARRIVE - Creating brand new state for user {user_id}")
        users[user_id] = UserState()
    
    # Reset locations but maintain user state
    for loc in locs.values():
        loc['items'] = []

    # Add fashion magazine only if user doesn't have it
    if not any(i.get('name') == 'fashion-magazine' for i in data.get('owned', [])) and \
       not any(i.get('name') == 'fashion-magazine' for i in data.get('dropped', [])):
        locs['shopping-area']['items'].append({
            'name': 'fashion-magazine',
            'id': item_ids[3],
            'description': domain_items[3]['description'],
            'verb': domain_items[3]['verb']
        })
    
    # Handle depth-based item placement
    for item in prizes:
        depth = item.get('depth', 0)
        if depth == 0:
            locs['accessories']['items'].append(item)
        elif depth == 1 or depth == 2:
            locs['vip-lounge']['items'].append(item)
            
    # Handle dropped items
    for item in data.get('dropped', []):
        loc = item['location']
        if isinstance(loc, tuple):
            loc = loc[1]
        locs[loc]['items'].append(item)
    
    # Place starting flyer if user doesn't have it
    if not any(i.get('name') == 'sales-flyer' for i in data.get('owned', [])) and \
       not any(i.get('name') == 'sales-flyer' for i in data.get('dropped', [])):
        locs['boutique-entrance']['items'].append({
            'name': 'sales-flyer',
            'id': item_ids[0],
            'description': domain_items[0]['description'],
            'verb': domain_items[0]['verb']
        })
    
    print(f"ARRIVE - Final keypad state: {users[user_id].keypad_locked}")
    return Response(status=200)

@routes.post('/dropped')
async def handle_dropped(req: Request) -> Response:
    data = await req.json()
   
    if data['secret'] != domain_secret:
        return Response(status=403)
       
    user_id = data['user']
    if user_id not in users:
        return Response(status=403)
   
    current_location = users[user_id].location
   
    # Store dropped item in current location's items list
    if 'item' in data:
        item_data = {
            'name': data['item']['name'],
            'id': data['item']['id'],
            'description': data['item'].get('description', ''),
            'verb': data['item'].get('verb', {})
        }
        locs[current_location]['items'].append(item_data)
   
    return json_response(users[user_id].location)




@routes.post("/command")
async def handle_command(req: Request) -> Response:
    data = await req.json()
    user_id = data['user']
   
    if user_id not in users:
        return Response(text="You have to journey to this domain before you can send it commands.")

    if users[user_id].has_departed:
        return Response(status=409, text="You have departed from this domain. You must arrive again before sending commands.")
       
    command = data['command']
    state = users[user_id]
    current_loc = locs[state.location]
   
    def cur_loc(name):
        return any(i['name'] == name for i in current_loc['items'])
       
    def get_cur_loc(name):
        return next((i for i in current_loc['items'] if i['name'] == name), None)
       
    if command[0] == 'look':
        if len(command) == 1:
            response = current_loc['description']
            if state.location == 'vip-lounge' and not state.keypad_locked:
                response += "\nThe VIP lounge contains exclusive items and a private styling area but youll need certain things to make it all the way through."
           
            # Show items in location
            for item in current_loc['items']:
                if (state.location != 'vip-lounge' or
                    not state.keypad_locked or
                    item.get('depth', 0) == 0):
                    if state.location == 'vip-lounge' and item.get('depth', 0) >= 1:
                        response += f"\nThere is a {item['name']} <sub>{item['id']}</sub> in the VIP section."
                    else:
                        response += f"\nThere is a {item['name']} <sub>{item['id']}</sub> here."
            return Response(text=response)
       
        # Handle look <item>
        else:
            item = command[1]
            if item == 'keypad' and state.location == 'vip-lounge':
                return Response(text="A sleek digital keypad guards the VIP area. It's waiting for a code... if only you had one maybe you read something on the sales-flyer about it... hint 'tell keypad ____")
               
            # Check inventory for items
            async with req.app.client.post(hub_url+'/query', json={
                'domain': domain_id,
                'secret': domain_secret,
                'user': user_id,
                'location': 'inventory'
            }) as resp:
                if resp.status == 200:
                    inventory = await resp.json()
                    if item == 'sales-flyer' and item_ids[0] in inventory:
                        return Response(text=domain_items[0]['description'])
                       
            if cur_loc(item):
                item_obj = get_cur_loc(item)
                if 'description' in item_obj:
                    return Response(text=item_obj['description'])
                       
            return Response(text="I don't know how to do that.")
   
    elif command[0] == 'read':
        item_name = command[1]
        async with req.app.client.post(hub_url+'/query', json={
            'domain': domain_id,
            'secret': domain_secret,
            'user': user_id,
            'location': 'inventory'
        }) as resp:
            if resp.status == 200:
                inventory = await resp.json()
                if item_ids[0] in inventory and item_name == 'sales-flyer':
                    return Response(text='The flyer reads <q>VIP Room Code: VIP123</q>')
          
        return Response(text="I don't know how to do that.")
   
    # elif command[0] == 'use':
    #     if len(command) >= 2:
    #         item_name = command[1]
    #         async with req.app.client.post(hub_url+'/query', json={
    #             'domain': domain_id,
    #             'secret': domain_secret,
    #             'user': user_id,
    #             'location': 'inventory'
    #         }) as resp:
    #             if resp.status == 200:
    #                 inventory = await resp.json()
    #                 if item_name == 'vip-card' and item_ids[1] in inventory:
    #                     if state.location == 'vip-lounge':
    #                         if not state.keypad_locked:
    #                             # Check inventory for depth-2 items
    #                             async with req.app.client.post(hub_url+'/query', json={
    #                                 'domain': domain_id,
    #                                 'secret': domain_secret,
    #                                 'user': user_id,
    #                                 'location': 'inventory'
    #                             }) as depth_resp:
    #                                 if depth_resp.status == 200:
    #                                     depth_inv = await depth_resp.json()
    #                                     # Get all depth-2 items from VIP section
    #                                     depth_2_items = [item['id'] for item in locs['vip-lounge']['items'] if item.get('depth') == 2]
    #                                     # Check if any depth-2 item is in inventory
    #                                     has_depth_2 = any(item_id in depth_inv for item_id in depth_2_items)
                                        
    #                                     if not has_depth_2:
    #                                         return Response(text="You need to take a special item from the VIP section first.")
                                        
    #                                     state.keypad_locked = False
    #                                     async with req.app.client.post(hub_url+'/score', json={
    #                                         'domain': domain_id,
    #                                         'secret': domain_secret,
    #                                         'user': user_id,
    #                                         'score': 1.0
    #                                     }) as score_resp:
    #                                         pass
    #                                     return Response(text="CONGRATULATIONS! You've won! You swipe the VIP card and enter the showroom with your special item!\n\nYour game score is now 1.0 - you've completed this domain!")
    #                             return Response(text="You need VIP access to take items from this area")
    elif command[0] == 'use':
        if len(command) >= 2:
            item_name = command[1]
            async with req.app.client.post(hub_url+'/query', json={
                'domain': domain_id,
                'secret': domain_secret,
                'user': user_id,
                'location': 'inventory'
            }) as resp:
                if resp.status == 200:
                    inventory = await resp.json()
                    if item_name == 'gold-card' and item_ids[1] in inventory:
                        if state.location == 'vip-lounge':
                            if not state.keypad_locked:
                                # check if they have a depth-2 item 
                                depth_2_items = [item_id for item_id in inventory 
                                            if item_id == item_ids[4]]  # diamond-necklace ID
                                
                                if depth_2_items:
                                    state.keypad_locked = False
                                    async with req.app.client.post(hub_url+'/score', json={
                                        'domain': domain_id,
                                        'secret': domain_secret,
                                        'user': user_id,
                                        'score': 1.0
                                    }) as score_resp:
                                        pass
                                    return Response(text="CONGRATULATIONS! You've won! You swipe the gold-card and enter the showroom with your special item!\n\nYour game score is now 1.0 - you've completed this domain!")
                                
                                return Response(text="You need to take the diamond-necklace from the VIP section first.")
                            return Response(text="You need to enter the correct keypad code first.")

               
    elif command[0] == 'take':
        if len(command) != 2:
            return Response(text="I don't know how to do that.")
            
        item_identifier = command[1]
        
        # Try to parse as item ID first
        try:
            item_id = int(item_identifier)
            # Find item by ID
            item = next((i for i in current_loc['items'] if str(i['id']) == str(item_id)), None)
            if item:
                item_name = item['name']
            else:
                return Response(text=f"There's no item with ID {item_id} here to take")
        except ValueError:
            # If not an ID, treat as item name
            item_name = item_identifier
            item = get_cur_loc(item_name)
            
            if not item:
                return Response(text=f"There's no {item_name} here to take")
                
        if state.location == 'vip-lounge' and state.keypad_locked:
            return Response(text=f"You need VIP access to take items from this area")
        
        if state.location == 'vip-lounge' and item.get('depth') == 2:
            # Check if they have a depth-0 item first
            async with req.app.client.post(hub_url+'/query', json={
                'domain': domain_id,
                'secret': domain_secret,
                'user': user_id,
                'location': 'inventory'
            }) as depth_resp:
                if depth_resp.status == 200:
                    inventory = await depth_resp.json()
                    if not any(str(item_id) in str(item_ids[1]) for item_id in inventory):
                        return Response(text="You need the gold-card to take special items.")
            
        async with req.app.client.post(hub_url+'/transfer', json={
            'domain': domain_id,
            'secret': domain_secret,
            'user': user_id,
            'item': item['id'],
            'to': 'inventory'
        }) as resp:
            if resp.status != 200:
                return Response(text="I don't know how to do that.")
                
        #current_loc['items'].remove(item)
        current_loc['items'] = [i for i in current_loc['items'] if i['id'] != item['id']]
        return Response(text=f"You take the {item_name}.")


   
    elif command[0] == 'go':
        if len(command) != 2:
            return Response(text="I don't know how to do that.")
           
        direction = command[1]
        if direction not in current_loc['exits']:
            return Response(text="You can't go that way from here.")
           
        new_loc = current_loc['exits'][direction]
        if new_loc == 'journey':
            return Response(text="$journey east")
           
        state.location = new_loc
        response = locs[new_loc]['description']
       
        for item in locs[new_loc]['items']:
            if (new_loc != 'vip-lounge' or
                not state.keypad_locked or
                item.get('depth', 0) == 0):
                if new_loc == 'vip-lounge' and item.get('depth', 0) >= 1:
                    response += f"\nThere is a {item['name']} <sub>{item['id']}</sub> in the VIP section."
                else:
                    response += f"\nThere is a {item['name']} <sub>{item['id']}</sub> here."
        return Response(text=response)
   
    elif command[0] == 'tell' and len(command) == 3 and command[1] == 'keypad':
        if state.location == 'vip-lounge':
            if command[2].upper() == 'VIP123':
                state.keypad_locked = False
                return Response(text='The keypad beeps in confirmation. Now you need to swipe your gold card to complete access to the VIP area to enter the private showroom!')
            else:
                return Response(text=f'You enter the code "{command[2]}" but nothing happens.')
        return Response(text="I don't know how to do that.")



##dont change this


@web.middleware
async def allow_cors(req, handler):
    """Bypass cross-origin resource sharing protections,
    allowing anyone to send messages from anywhere.
    Generally unsafe, but for this class project it should be OK."""
    resp = await handler(req)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


async def start_session(app):
    """To be run on startup of each event loop. Makes singleton ClientSession"""
    from aiohttp import ClientSession, ClientTimeout
    app.client = ClientSession(timeout=ClientTimeout(total=3))


async def end_session(app):
    """To be run on shutdown of each event loop. Closes the singleton ClientSession"""
    await app.client.close()




if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default="0.0.0.0")
    parser.add_argument('-p','--port', type=int, default=3400)
    args = parser.parse_args()


    import socket
    whoami = socket.getfqdn()
    if '.' not in whoami: whoami = 'localhost'
    whoami += ':'+str(args.port)
    whoami = 'http://' + whoami
    print("URL to type into web prompt:\n\t"+whoami)
    print()


    app = web.Application(middlewares=[allow_cors])
    app.on_startup.append(start_session)
    app.on_shutdown.append(end_session)
    app.add_routes(routes)
    web.run_app(app, host=args.host, port=args.port)
