from werkzeug.security import generate_password_hash, check_password_hash
from extensions import mongo
from datetime import datetime, timezone, timedelta
from bson import ObjectId

class User:
    def __init__(self, username, password, role='doctor'):
        self.username = username
        self.password_hash = generate_password_hash(password)
        self.role = role

    @staticmethod
    def ensure_timezone_aware(dt):
        """Ensure datetime is timezone-aware by adding UTC if naive"""
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def create_user(username, password, role='doctor'):
        if mongo.db.users.find_one({'username': username}):
            return False
        
        user = User(username, password, role)
        mongo.db.users.insert_one({
            'username': user.username,
            'password': user.password_hash,
            'role': user.role,
            'created_at': datetime.now(timezone.utc)
        })
        return True

    @staticmethod
    def get_user(username):
        user_data = mongo.db.users.find_one({'username': username})
        if not user_data:
            return None
        return user_data

    @staticmethod
    def verify_password(username, password):
        user_data = User.get_user(username)
        if not user_data:
            return False
        return check_password_hash(user_data['password'], password)

    @staticmethod
    def start_consultation(doctor_username, record_id):
        """Start a consultation timer"""
        # Check if there's already an active consultation
        active = mongo.db.consultations.find_one({
            'doctor_username': doctor_username,
            'status': 'active'
        })
        if active:
            return None

        consultation = {
            'doctor_username': doctor_username,
            'record_id': record_id,
            'start_time': datetime.now(timezone.utc),
            'status': 'active'
        }
        result = mongo.db.consultations.insert_one(consultation)
        return str(result.inserted_id)

    @staticmethod
    def end_consultation(consultation_id, doctor_username):
        """End a consultation and calculate duration"""
        end_time = datetime.now(timezone.utc)
        
        # Find and update the consultation
        consultation = mongo.db.consultations.find_one({
            '_id': ObjectId(consultation_id),
            'doctor_username': doctor_username,
            'status': 'active'
        })
        
        if not consultation:
            return None
        
        # Ensure start_time is timezone-aware
        start_time = User.ensure_timezone_aware(consultation['start_time'])
        duration = (end_time - start_time).total_seconds()
        
        # Update consultation with end time and duration
        mongo.db.consultations.update_one(
            {'_id': ObjectId(consultation_id)},
            {
                '$set': {
                    'end_time': end_time,
                    'duration': duration,
                    'status': 'completed'
                }
            }
        )
        
        return duration

    @staticmethod
    def get_consultation_metrics(doctor_username):
        """Get consultation time metrics for a doctor"""
        pipeline = [
            {
                '$match': {
                    'doctor_username': doctor_username,
                    'status': 'completed'
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total_consultations': {'$sum': 1},
                    'avg_duration': {'$avg': '$duration'},
                    'min_duration': {'$min': '$duration'},
                    'max_duration': {'$max': '$duration'}
                }
            }
        ]
        
        result = list(mongo.db.consultations.aggregate(pipeline))
        
        if result:
            metrics = result[0]
            return {
                'total_consultations': metrics['total_consultations'],
                'avg_minutes': round(metrics['avg_duration'] / 60, 2),
                'min_minutes': round(metrics['min_duration'] / 60, 2),
                'max_minutes': round(metrics['max_duration'] / 60, 2)
            }
        
        return {
            'total_consultations': 0,
            'avg_minutes': 0,
            'min_minutes': 0,
            'max_minutes': 0
        }

    @staticmethod
    def get_active_consultation(doctor_username):
        """Get active consultation for a doctor"""
        return mongo.db.consultations.find_one({
            'doctor_username': doctor_username,
            'status': 'active'
        })

    @staticmethod
    def get_performance_metrics(doctor_username, period_type):
        """Get performance metrics for different time periods"""
        now = datetime.now(timezone.utc)
        
        if period_type == 'weekly':
            start_date = now - timedelta(days=7)
            group_format = '%Y-%U'  # Week number format
        elif period_type == 'monthly':
            start_date = now - timedelta(days=30)
            group_format = '%Y-%m'  # Month format
        elif period_type == 'yearly':
            start_date = now - timedelta(days=365)
            group_format = '%Y'  # Year format
        else:
            raise ValueError('Invalid period type')

        pipeline = [
            {
                '$match': {
                    'doctor_username': doctor_username,
                    'start_time': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': {
                        'period': {'$dateToString': {'format': group_format, 'date': '$start_time'}},
                        'status': '$status'
                    },
                    'count': {'$sum': 1},
                    'avg_duration': {
                        '$avg': {
                            '$cond': [
                                {'$eq': ['$status', 'completed']},
                                '$duration',
                                None
                            ]
                        }
                    }
                }
            },
            {
                '$group': {
                    '_id': '$_id.period',
                    'metrics': {
                        '$push': {
                            'status': '$_id.status',
                            'count': '$count',
                            'avg_duration': '$avg_duration'
                        }
                    }
                }
            },
            {'$sort': {'_id': 1}}
        ]

        results = list(mongo.db.consultations.aggregate(pipeline))
        
        # Format results
        formatted_results = []
        for result in results:
            period_metrics = {
                'period': result['_id'],
                'total_records': 0,
                'completed_cases': 0,
                'avg_duration_minutes': 0
            }
            
            for metric in result['metrics']:
                if metric['status'] == 'completed':
                    period_metrics['completed_cases'] = metric['count']
                    if metric['avg_duration']:
                        period_metrics['avg_duration_minutes'] = round(metric['avg_duration'] / 60, 2)
                period_metrics['total_records'] += metric['count']
                
            formatted_results.append(period_metrics)
            
        return formatted_results

    @staticmethod
    def get_daily_hourly_breakdown(doctor_username, date=None):
        """Get hourly consultation breakdown for a specific date"""
        if date is None:
            date = datetime.now(timezone.utc)
        else:
            # Convert string date to datetime if needed
            if isinstance(date, str):
                date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                
        # Start and end of the specified date in UTC
        start_of_day = datetime.combine(date.date(), datetime.min.time(), tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)

        pipeline = [
            {
                '$match': {
                    'doctor_username': doctor_username,
                    'start_time': {
                        '$gte': start_of_day,
                        '$lt': end_of_day
                    }
                }
            },
            {
                '$group': {
                    '_id': {
                        'hour': {'$hour': '$start_time'},
                        'status': '$status'
                    },
                    'count': {'$sum': 1},
                    'avg_duration': {
                        '$avg': {
                            '$cond': [
                                {'$eq': ['$status', 'completed']},
                                '$duration',
                                None
                            ]
                        }
                    }
                }
            },
            {
                '$group': {
                    '_id': '$_id.hour',
                    'metrics': {
                        '$push': {
                            'status': '$_id.status',
                            'count': '$count',
                            'avg_duration': '$avg_duration'
                        }
                    }
                }
            },
            {'$sort': {'_id': 1}}
        ]

        results = list(mongo.db.consultations.aggregate(pipeline))
        
        # Initialize hourly metrics for all 24 hours
        hourly_metrics = {
            str(hour).zfill(2): {
                'hour': str(hour).zfill(2),
                'total_records': 0,
                'completed_cases': 0,
                'avg_duration_minutes': 0
            }
            for hour in range(24)
        }
        
        # Fill in actual data
        for result in results:
            hour = str(result['_id']).zfill(2)
            for metric in result['metrics']:
                if metric['status'] == 'completed':
                    hourly_metrics[hour]['completed_cases'] = metric['count']
                    if metric['avg_duration']:
                        hourly_metrics[hour]['avg_duration_minutes'] = round(metric['avg_duration'] / 60, 2)
                hourly_metrics[hour]['total_records'] += metric['count']
        
        return list(hourly_metrics.values())