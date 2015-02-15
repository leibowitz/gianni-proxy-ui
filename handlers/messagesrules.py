from base import BaseRequestHandler

class MessagesRulesHandler(BaseRequestHandler):
    def get_rules(self):
        x = 0
        rid = self.get_argument('rules_ids[' + str(x) + ']', None)
        rstate = self.get_argument('rules_states[' + str(x) + ']', False)
        rstate = False if rstate == False else True
        rules = []
        
        while rid is not None:
            rules.append([rid, rstate])
            x = x + 1
            rid = self.get_argument('rules_ids[' + str(x) + ']', None)
            rstate = self.get_argument('rules_states[' + str(x) + ']', False)
            rstate = False if rstate == False else True

        return dict([[rid, rstate] for rid, rstate in rules if rid])

