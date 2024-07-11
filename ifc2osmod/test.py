import numpy as np

x = np.identity(4)
x[:, 3] = [1, .05, 0, 0]
print(x)