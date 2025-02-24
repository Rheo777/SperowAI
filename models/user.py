from werkzeug.security import generate_password_hash, check_password_hash
from extensions import mongo
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import re

class User:
    def __init__(self, email, password, role='doctor'):
        self.email = email.lower()  # Store email in lowercase
        self.password_hash = generate_password_hash(password)
        self.role = role

    @staticmethod
    def ensure_timezone_aware(dt):
        """Ensure datetime is timezone-aware by adding UTC if naive"""
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def is_valid_email(email):
        """Validate email format"""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return bool(email_pattern.match(email))

    @staticmethod
    def create_user(email, password, role='doctor'):
        if not User.is_valid_email(email):
            return False, "Invalid email format"
            
        email = email.lower()
        if mongo.db.users.find_one({'email': email}):
            return False, "Email already exists"
        
        user = User(email, password, role)
        mongo.db.users.insert_one({
            'email': user.email,
            'password': user.password_hash,
            'role': user.role,
            'created_at': datetime.now(timezone.utc),
            'last_login': None
        })
        return True, "User created successfully"

    @staticmethod
    def verify_password(email, password):
        email = email.lower()
        user = mongo.db.users.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            # Update last login time
            mongo.db.users.update_one(
                {'email': email},
                {
                    '$set': {
                        'last_login': datetime.now(timezone.utc),
                        'last_login_ip': None  # Can be set if IP tracking is needed
                    }
                }
            )
            return True
        return False

    @staticmethod
    def get_user_by_email(email):
        email = email.lower()
        return mongo.db.users.find_one({'email': email})

    @staticmethod
    def start_consultation(doctor_email, record_id):
        """Start a consultation timer"""
        # Check if there's already an active consultation
        active = mongo.db.consultations.find_one({
            'doctor_email': doctor_email,
            'status': 'active'
        })
        if active:
            return None

        consultation = {
            'doctor_email': doctor_email,
            'record_id': record_id,
            'start_time': datetime.now(timezone.utc),
            'status': 'active'
        }
        result = mongo.db.consultations.insert_one(consultation)
        return str(result.inserted_id)

    @staticmethod
    def end_consultation(consultation_id, doctor_email):
        """End a consultation and calculate duration"""
        end_time = datetime.now(timezone.utc)
        
        # Find and update the consultation
        consultation = mongo.db.consultations.find_one({
            '_id': ObjectId(consultation_id),
            'doctor_email': doctor_email,
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
    def get_consultation_metrics(doctor_email):
        """Get consultation time metrics for a doctor"""
        pipeline = [
            {
                '$match': {
                    'doctor_email': doctor_email,
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
    def get_active_consultation(doctor_email):
        """Get active consultation for a doctor"""
        return mongo.db.consultations.find_one({
            'doctor_email': doctor_email,
            'status': 'active'
        })

    @staticmethod
    def get_performance_metrics(doctor_email, period_type, year=None, month=None, week=None):
        """Get performance metrics for different time periods"""
        now = datetime.now(timezone.utc)
        
        if period_type == 'weekly':
            if not year or not month or not week:
                start_date = now - timedelta(days=7)
                end_date = now
            else:
                # Get the first day of the specified week in the month
                first_day = datetime.strptime(f"{year}-{month}-1", "%Y-%m-%d")
                start_date = first_day + timedelta(weeks=int(week))
                end_date = start_date + timedelta(days=7)
                
            pipeline = [
                {
                    '$match': {
                        'doctor_email': doctor_email,
                        'status': 'completed',
                        'start_time': {
                            '$gte': start_date,
                            '$lt': end_date
                        }
                    }
                },
                {
                    '$group': {
                        '_id': {
                            'dayOfWeek': {'$dayOfWeek': '$start_time'}  # 1 for Sunday through 7 for Saturday
                        },
                        'completed_cases': {'$sum': 1}
                    }
                },
                {'$sort': {'_id.dayOfWeek': 1}}
            ]
            
            results = list(mongo.db.consultations.aggregate(pipeline))
            
            # Initialize metrics for all days
            days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            daily_metrics = {day: 0 for day in days}
            
            # Fill in actual data
            for result in results:
                day_index = result['_id']['dayOfWeek'] - 1  # Convert 1-7 to 0-6
                daily_metrics[days[day_index]] = result['completed_cases']
            
            return {
                'period_type': 'weekly',
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'daily_metrics': daily_metrics
            }
            
        elif period_type == 'monthly':
            if not year or not month:
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = (start_date + timedelta(days=32)).replace(day=1)
            else:
                start_date = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
                end_date = (start_date + timedelta(days=32)).replace(day=1)
                
            pipeline = [
                {
                    '$match': {
                        'doctor_email': doctor_email,
                        'status': 'completed',
                        'start_time': {
                            '$gte': start_date,
                            '$lt': end_date
                        }
                    }
                },
                {
                    '$group': {
                        '_id': {
                            'week': {'$week': '$start_time'}
                        },
                        'completed_cases': {'$sum': 1}
                    }
                },
                {'$sort': {'_id.week': 1}}
            ]
            
            results = list(mongo.db.consultations.aggregate(pipeline))
            
            # Initialize metrics for all weeks
            weekly_metrics = {f'Week {i}': 0 for i in range(6)}  # Assuming max 6 weeks in a month
            
            # Fill in actual data
            for result in results:
                week_num = result['_id']['week']
                relative_week = week_num - results[0]['_id']['week']  # Make week numbers relative to first week
                weekly_metrics[f'Week {relative_week}'] = result['completed_cases']
            
            return {
                'period_type': 'monthly',
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'weekly_metrics': weekly_metrics
            }
            
        elif period_type == 'yearly':
            if not year:
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date.replace(year=start_date.year + 1)
            else:
                start_date = datetime(int(year), 1, 1, tzinfo=timezone.utc)
                end_date = datetime(int(year) + 1, 1, 1, tzinfo=timezone.utc)
                
            pipeline = [
                {
                    '$match': {
                        'doctor_email': doctor_email,
                        'status': 'completed',
                        'start_time': {
                            '$gte': start_date,
                            '$lt': end_date
                        }
                    }
                },
                {
                    '$group': {
                        '_id': {
                            'month': {'$month': '$start_time'}
                        },
                        'completed_cases': {'$sum': 1}
                    }
                },
                {'$sort': {'_id.month': 1}}
            ]
            
            results = list(mongo.db.consultations.aggregate(pipeline))
            
            # Initialize metrics for all months
            months = ['January', 'February', 'March', 'April', 'May', 'June', 
                     'July', 'August', 'September', 'October', 'November', 'December']
            monthly_metrics = {month: 0 for month in months}
            
            # Fill in actual data
            for result in results:
                month_index = result['_id']['month'] - 1  # Convert 1-12 to 0-11
                monthly_metrics[months[month_index]] = result['completed_cases']
            
            return {
                'period_type': 'yearly',
                'year': start_date.year,
                'monthly_metrics': monthly_metrics
            }
        
        else:
            raise ValueError('Invalid period type')

    @staticmethod
    def get_daily_hourly_breakdown(doctor_email, date=None):
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
                    'doctor_email': doctor_email,
                    'status': 'completed',
                    'start_time': {
                        '$gte': start_of_day,
                        '$lt': end_of_day
                    }
                }
            },
            {
                '$group': {
                    '_id': {
                        'hour': {'$hour': '$start_time'}
                    },
                    'completed_cases': {'$sum': 1}
                }
            },
            {'$sort': {'_id.hour': 1}}
        ]

        results = list(mongo.db.consultations.aggregate(pipeline))
        
        # Initialize hourly metrics for all hours
        hourly_metrics = []
        for hour in range(24):
            start_hour = f"{hour:02d}:00"
            end_hour = f"{(hour + 1):02d}:00"
            hourly_metrics.append({
                'time_range': f"{start_hour}-{end_hour}",
                'completed_cases': 0
            })
        
        # Fill in actual data
        for result in results:
            hour = result['_id']['hour']
            hourly_metrics[hour]['completed_cases'] = result['completed_cases']
        
        return {
            'date': start_of_day.date().isoformat(),
            'hourly_metrics': hourly_metrics
        }