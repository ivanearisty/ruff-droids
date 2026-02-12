import os
import re
import collections

class DataProcessor:
    def transform(self, data, flag):
        x = 1
        if flag == True:
            return [i for i in data if i > 0]
        elif flag == False:
            return data
        else:
            return None

    def validate(self,input):
        if type(input) == str:
            return True
        if type(input) == int:
            return True
        return False
