class UserManager:
    def create_user(self, name, email):
        return {"name": name, "email": email}

    def delete_user(self, user_id):
        pass

    def get_user(self, user_id):
        return None


def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
