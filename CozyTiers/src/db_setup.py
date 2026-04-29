import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = db.cursor()

# Create database if not exists
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
cursor.execute(f"USE {DB_NAME}")

# Servers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS servers (
    guild_id BIGINT PRIMARY KEY,
    guild_name VARCHAR(255),
    guild_icon VARCHAR(255),
    owner_id BIGINT,
    listing_name VARCHAR(255),
    listings_logo VARCHAR(255),
    app_logs_channel BIGINT,
    tier_staff_role BIGINT
)
""")

# Testers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS testers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT,
    user_id BIGINT,
    region VARCHAR(10),
    standout TEXT,
    status ENUM('pending', 'approved', 'rejected'),
    reason TEXT,
    tester_tier VARCHAR(10) DEFAULT 'LT5',
    completed_tests INT DEFAULT 0,
    FOREIGN KEY (guild_id) REFERENCES servers(guild_id)
)
""")

# Reviews table
cursor.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT,
    user_id BIGINT,
    tester_id BIGINT,
    rating INT,
    comment TEXT,
    FOREIGN KEY (guild_id) REFERENCES servers(guild_id)
)
""")

# Tiers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS tiers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT,
    user_id BIGINT,
    tier VARCHAR(50),
    role_id BIGINT,
    FOREIGN KEY (guild_id) REFERENCES servers(guild_id)
)
""")

# Tier roles table
cursor.execute("""
CREATE TABLE IF NOT EXISTS tier_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT,
    role_name VARCHAR(255),
    role_id BIGINT,
    points INT,
    FOREIGN KEY (guild_id) REFERENCES servers(guild_id)
)
""")

# Queue table (temporary)
cursor.execute("""
CREATE TABLE IF NOT EXISTS queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT,
    user_id BIGINT,
    tester_id BIGINT,
    status ENUM('waiting', 'assigned', 'completed'),
    FOREIGN KEY (guild_id) REFERENCES servers(guild_id)
)
""")

db.commit()

print("Database setup complete.")

# Function to close the database connection cleanly
def close_db():
    """Close the database connection when the bot shuts down"""
    try:
        cursor.close()
        db.close()
        print("Database connection closed.")
    except Exception as e:
        print(f"Error closing database: {e}")