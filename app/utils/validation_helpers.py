from fastapi import HTTPException, status


def validate_start_time(value):
    if value and (value.minute != 0 or value.second != 0 or value.microsecond != 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be at the beginning of an hour (e.g., 13:00:00)",
        )
    return value
