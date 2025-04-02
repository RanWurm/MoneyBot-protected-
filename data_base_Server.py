from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

mongodb_uri = os.getenv("MONGODB_URI")
client = MongoClient(mongodb_uri)

db = client["MoneyBot"]
collection = db["deals"]

@app.route('/add-new-group', methods=['POST'])
def add_new_group():
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Group name is required'}), 400
    
    group_name = data['name']
    
    # Check if group already exists
    existing_group = collection.find_one({'name': group_name})
    if existing_group:
        return jsonify({'message': 'Group already exists'}), 200
    
    # Create new group with initial values
    new_group = {
        'name': group_name,
        'winnings': 0,
        'loses': 0,
        'avg_payout': 0.0
    }
    
    collection.insert_one(new_group)
    return jsonify({'message': 'Group created successfully'}), 201

@app.route('/get-stats/<group>', methods=['GET'])
def get_stats(group):
    group_data = collection.find_one({'name': group})
    
    if not group_data:
        return jsonify({'error': 'Group not found'}), 404
    
    # Convert ObjectId to string for JSON serialization
    group_data['_id'] = str(group_data['_id'])
    
    return jsonify(group_data), 200
@app.route('/groupStat/', methods=['PUT'])
def update_group():
    data = request.get_json()
    if not data or 'group' not in data:
        return jsonify({'error': 'Group name is required'}), 400
    
    group_name = data['group']
    group = collection.find_one({'name': group_name})
    
    # If group doesn't exist, create it
    if not group:
        new_group = {
            'name': group_name,
            'winnings': 0,
            'loses': 0,
            'avg_payout': 0.0
        }
        collection.insert_one(new_group)
        group = new_group
    
    # Get current stats
    current_winnings = group.get('winnings', 0)
    current_loses = group.get('loses', 0)
    current_avg_payout = group.get('avg_payout', 0.0)
    
    # Check if winning status is provided
    if 'status' in data:
        # Handle string values
        status = data['status']
        
        # Convert string to boolean
        is_win = status.lower() == 'win'
            
        if is_win:
            current_winnings += 1
        else:
            current_loses += 1
    
    # Calculate new average payout if provided
    if 'pay_out' in data:
        payout = float(data['pay_out'])
        total_trades = current_winnings + current_loses
        
        if total_trades > 0:
            # Calculate weighted average
            current_avg_payout = ((current_avg_payout * (total_trades - 1)) + payout) / total_trades
    
    # Update the group
    update_data = {
        'winnings': current_winnings,
        'loses': current_loses,
        'avg_payout': current_avg_payout
    }
    
    collection.update_one({'name': group_name}, {'$set': update_data})
    
    return jsonify({'message': 'Group updated successfully'}), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'Server is running'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
