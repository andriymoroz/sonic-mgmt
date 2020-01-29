import pytest
import logging


@pytest.fixture(scope='module', autouse=True)
def max_lane_speed(request):
    """
    Fixture send --max_lane_speed value from command line or 25000 as the default value
    :return: Max lane speed
    :rtype: int
    """
    max_lane_speed_value = request.config.getoption("--max_lane_speed")
    return int(max_lane_speed_value)


@pytest.fixture(scope='function', autouse=True)
def ports_data(duthost):
    """
    Fixture prepare data about up ports with lanes and restore start speed after test execution
    :param duthost: Sonic environment
    :type duthost: SonicHost
    """
    ports_list_text = duthost.command('redis-cli -n 0 keys "*PORT*"')['stdout']
    all_ports = ports_list_text.split('\n')
    all_ports_data = [get_port_data(duthost, port) for port in all_ports]
    up_ports = [port_data for port_data in all_ports_data if bool(port_data)]
    yield up_ports
    for port in up_ports:
        change_speed(duthost, port['name'], port['speed'])


def test_speed(duthost, max_lane_speed, ports_data):
    """
    Test speed for all possible speeds on all appropriate ports. The test is failed if minimally 1 port test failed.
    :param duthost: SonicHost Sonic environment
    :param max_lane_speed maximal possible lane speed
    :param ports_data Data about available ports (admin status, lanes quantity, port name, operational status,
    current speed)
    :type duthost: SonicHost
    :type max_lane_speed: int
    :type ports_data list[dict]
    """
    available_lane_speed = [10000, 25000]
    unavailable_speed = [20000]
    failed_asserts = []
    for port in ports_data:
        for lane_speed in available_lane_speed:
            current_speed = port['lanes_qty'] * lane_speed
            if lane_speed <= max_lane_speed and current_speed not in unavailable_speed:
                logging.info('Test for %s with speed: %s' % (port['name'], current_speed))
                change_speed(duthost, port['name'], current_speed)
                try:
                    port_changed_data = get_port_data(duthost, port['name'])
                    assert port_changed_data['oper_status'] == 'up'
                    assert port_changed_data['admin_status'] == 'up'
                    assert int(port_changed_data['speed']) == current_speed
                except AssertionError as e:
                    assert_message = 'Port: %s, speed: %s: %s' % (port['name'], current_speed, str(e))
                    failed_asserts.append(assert_message)
    assert not bool(failed_asserts), str(failed_asserts)


def get_port_data(duthost, port_name):
    """
    Returns data about a port
    :param duthost: Sonic environment
    :param port_name: The name of the requiring port
    :type duthost: SonicHost
    :type port_name: str
    :return Dictionary with port data (admin status, lanes quantity, port name, operational status, current speed) or
    empty dictionary for an invalid port
    :rtype: dict
    """
    port_data = redis_hgetall(duthost, 0, port_name)
    current_oper_status = port_data.get('oper_status')
    current_admin_status = port_data.get('admin_status')
    lanes_txt = port_data.get('lanes')
    if current_oper_status == 'up' and current_admin_status == 'up' and lanes_txt:
        lanes_qty = len(lanes_txt.split(','))
        start_speed = port_data['speed']
        return {
            'admin_status': current_admin_status,
            'lanes_qty': lanes_qty,
            'name': port_name,
            'oper_status': current_oper_status,
            'speed': start_speed,
        }
    else:
        return {}


def redis_hgetall(duthost, base_number, key):
    """
        Extracts all data for specific base and key
    :param duthost: Sonic environment
    :param base_number: number of a base
    :param key: record key
    :type duthost: SonicHost
    :type base_number: int
    :type key: str
    :return: Dictionary with all information
    :rtype: dict
    """
    port_data_list = duthost.command('redis-cli -n {base_number} HGETALL {key}'.format(
        base_number=base_number,
        key=key,
    ))['stdout'].split('\n')
    port_data_dict = {}
    for i in range(0, len(port_data_list), 2):
        port_data_dict[port_data_list[i]] = port_data_list[i+1]
    return port_data_dict


def change_speed(duthost, port, speed):
    """
        Changes a speed on Sonic and on fanout for a port
    :param duthost: Sonic environment
    :param port: A port name
    :param speed: A port speed
    :type duthost: SonicHost
    :type port: str
    :type speed: int
    """
    interface_name = port.split(':')[-1]
    duthost.command('sudo config interface speed "%s" %s' % (interface_name, speed))
    change_fanout_speed(port, speed)


def change_fanout_speed(port, speed):
    # TODO after adding functionality of entering fan_out add changing speed of related port
    pass
