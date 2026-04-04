class Demo:
    def outer(self):
        x = 10
        self.inner()   # calling another method

    def inner(self):
        print(x)   # ❌ won't work
    outer()