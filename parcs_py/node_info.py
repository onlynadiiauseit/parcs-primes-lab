import os
import platform


class NodeInfo:
    def __init__(self, cpu, ram):
        self.cpu, self.ram = cpu, ram

    def serialize(self):
        return {'cpu': self.cpu, 'ram': self.ram}


def get_node_info_for_current_machine():
    cpu = platform.processor() or platform.machine()
    try:
        with open('/proc/cpuinfo') as source:
            cpu = next(line.split(':', 1)[1].strip() for line in source
                       if line.startswith('model name'))
    except (OSError, StopIteration):
        pass
    ram = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**30
    return NodeInfo(cpu, f'{ram:.1f} GiB')


def create_node_info(data):
    return NodeInfo(data['cpu'], data['ram'])
