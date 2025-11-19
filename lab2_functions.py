import math
import re

def is_palindrome(text: str) -> bool:
    # Ignorujemy wielkość liter i spacje
    cleaned = re.sub(r'\s+', '', text.lower())
    return cleaned == cleaned[::-1]

def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("n musi być większe bądź równe 0")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def count_vowels(text: str) -> int:
    # Uwzględniamy polskie znaki, jeśli chcesz tylko aeiouy, usuń znaki diakrytyczne
    vowels = "aeiouyąęóAEIOUYĄĘÓ"
    return sum(1 for char in text if char in vowels)

def calculate_discount(price: float, discount: float) -> float:
    if not (0 <= discount <= 1):
        raise ValueError("Discount must be between 0 and 1")
    return price * (1 - discount)

def flatten_list(nested_list: list) -> list:
    result = []
    for item in nested_list:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result

def word_frequencies(text: str) -> dict:
    # Ignorujemy wielkość liter i interpunkcję
    words = re.findall(r'\b\w+\b', text.lower())
    freq = {}
    for word in words:
        freq[word] = freq.get(word, 0) + 1
    return freq

def is_prime(n: int) -> bool:
    if(n<2):
        return False
    for i in range(2, int(math.sqrt(n)) + 1):
        if(n % i == 0):
            return False
    return True