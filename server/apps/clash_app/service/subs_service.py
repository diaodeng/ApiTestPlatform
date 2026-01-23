

class SubsService:
    @classmethod
    async def get_subs(cls):
        return await SubsService.get_subs()

    @classmethod
    async def create_sub(cls, data, user):
        pass

    @classmethod
    async def delete_sub(cls, sub_id):
        pass

    @classmethod
    async def update_sub(cls, data, user):
        pass

    @classmethod
    async def get_sub(cls, sub_id):
        pass

    @classmethod
    async def fetch_sub(cls, sub_id):
        pass

    @classmethod
    async def assert_not_bound(cls, sub_id):
        pass