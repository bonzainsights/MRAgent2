class Student:
    def __init__(self, name, student_id):
        self.name = name
        self.student_id = student_id
        self.grades = {}

    def add_grade(self, subject, grade):
        if not (0 <= grade <= 100):
            raise ValueError("Grade must be between 0 and 100.")
        self.grades[subject] = grade

    def get_grade(self, subject):
        return self.grades.get(subject, None)

    def calculate_average(self):
        if not self.grades:
            return 0.0
        return sum(self.grades.values()) / len(self.grades)

    def __str__(self):
        return f"Student(Name: {self.name}, ID: {self.student_id}, Grades: {self.grades})"


# Example usage:
if __name__ == "__main__":
    # Create a student
    student = Student("Alice", "S12345")
    
    # Add grades
    student.add_grade("Math", 95)
    student.add_grade("Science", 87)
    student.add_grade("English", 92)
    
    # Print student details
    print(student)
    
    # Get a specific grade
    print(f"Math Grade: {student.get_grade('Math')}")
    
    # Calculate average
    print(f"Average Grade: {student.calculate_average():.2f}")