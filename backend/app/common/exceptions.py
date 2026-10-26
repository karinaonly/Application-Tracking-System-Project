from fastapi import HTTPException, status

class ParsingError(Exception):
    def __init__(self, message: str = "Document parsing error"):
        self.message = message
        super().__init__(self.message)

class ResumeNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

class JobNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Job description not found")
