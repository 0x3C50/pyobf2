print("A simple test")


def func():
    print("this is a function")


def funcp1(p):
    print("This is a function with a param", p)


def funcp2(p, p1):
    print(p, p1)


local = ["this", "is", "a", "local"]
print(" ".join(local))
func()
funcp1("This is an argument")
funcp2("This is a function with 2 args", "and this is arg 2")