from datetime import datetime
a = datetime.now()
for i in range(100000000) : 
    x = 2
b = datetime.now()
print(a)
print(b)
a = b - a
y = a.microseconds
x = a.seconds
print(x)
print(y)