class Player:
    def __init__(self, season_year, name, escalao, n_carteira, dob, mobile_phone, email):
        self.season_year = season_year
        self.name = name
        self.escalao = escalao
        self.n_carteira = n_carteira
        self.dob = dob
        self.mobile_phone = mobile_phone
        self.email = email

    def to_dict(self):
        return self.__dict__