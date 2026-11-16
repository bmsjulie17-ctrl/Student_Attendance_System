
from werkzeug.security import generate_password_hash
from db import get_db_connection

student_name = "Arun Kumar"
email = "arun@gmail.com"

password = input("Enter a new password for Arun: ")

connection = get_db_connection()
cursor = connection.cursor()

hashed_password = generate_password_hash(password)

cursor.execute(
    """
    INSERT INTO users (name, email, password, user_type)
    VALUES (%s, %s, %s, %s)
    """,
    (student_name, email, hashed_password, "Student")
)

connection.commit()

cursor.close()
connection.close()

print("Arun Kumar Student Login created successfully!")
