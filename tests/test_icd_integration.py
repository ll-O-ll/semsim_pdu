"""
PDU ICD Integration Test
Tests OBC-to-SEMSIM communication via TCP/IP with ICD-compliant commands and responses

PREREQUISITES:
    1. Start SEMSIM server in a separate terminal:
       python semsim.py --mode simulator --tcp-ip 127.0.0.1 --tcp-port 5004
    
    2. Wait for server to be ready (you'll see "TMTC Manager started")
    
    3. Run this test:
       python -m pytest tests/test_icd_integration.py -v
       OR
       python tests/test_icd_integration.py
"""
import unittest
import socket
import json
import time

# Test configuration
TEST_IP = "127.0.0.1"
TEST_PORT = 5004
APID = 0x100  # PDU APID


class TestPduIcdIntegration(unittest.TestCase):
    """Integration test for PDU ICD compliance"""
    
    def setUp(self):
        """Create UDP socket for each test"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(5.0)  # 5 second timeout
        self.sequence_count = 0
        
        # Test connection to SEMSIM
        try:
            self.send_command({"ObcHeartBeat": {"HeartBeat": 0}}, packet_type=3, subtype=1)
            print("\n✓ Connected to SEMSIM server")
        except socket.timeout:
            self.fail("Cannot connect to SEMSIM server. Please start SEMSIM first:\n"
                     f"  python semsim.py --mode simulator --tcp-ip {TEST_IP} --tcp-port {TEST_PORT}")
    
    def tearDown(self):
        """Close socket after each test"""
        if self.socket:
            self.socket.close()
    
    def create_space_packet(self, command_json, packet_type=1, subtype=1):
        """Create CCSDS Space Packet for command"""
        command_bytes = bytes(command_json, 'utf-8')
        packet_data_length = len(command_bytes)
        
        # Packet version (3 bits) = 0
        # Packet type (1 bit) = 1 (telecommand)
        # Secondary header flag (1 bit) = 1
        # APID (11 bits)
        tc_version = 0x00
        tc_type = 0x01
        tc_dfh_flag = 0x01
        tc_apid = APID
        
        # Sequence flags (2 bits) = 11 (unsegmented)
        # Sequence count (14 bits)
        tc_seq_flag = 0x03
        tc_seq_count = self.sequence_count
        self.sequence_count = (self.sequence_count + 1) % 16384
        
        # Data field header (12 bytes)
        data_field_header = [0x10, packet_type, subtype, 0x00]
        data_pack_cuck = [0x2F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        data_field_header_frame = data_field_header + data_pack_cuck
        
        packet_header_length = len(data_field_header_frame)
        packet_data_length_field = packet_header_length + packet_data_length - 1
        
        # Build packet
        packet = bytes([
            (tc_version << 5) | (tc_type << 4) | (tc_dfh_flag << 3) | (tc_apid >> 8),
            (tc_apid & 0xFF),
            (tc_seq_flag << 6) | (tc_seq_count >> 8),
            (tc_seq_count & 0xFF),
            (packet_data_length_field >> 8),
            (packet_data_length_field & 0xFF)
        ])
        
        # Add data field header
        for byte_val in data_field_header_frame:
            packet += byte_val.to_bytes(1, 'big')
        
        # Add command payload
        packet += command_bytes
        
        return packet
    
    def decode_space_packet(self, packet):
        """Decode CCSDS Space Packet response"""
        if len(packet) < 6:
            return None, None, None, None
        
        # Parse header
        packet_type = (packet[0] >> 4) & 0x01
        apid = ((packet[0] & 0x07) << 8) | packet[1]
        sequence_count = ((packet[2] & 0x3F) << 8) | packet[3]
        packet_data_length = (packet[4] << 8) | packet[5] + 1
        
        # Parse data field header
        if len(packet) < 18:
            return None, None, None, None
        
        msg_type = packet[7]
        subtype = packet[8]
        
        # Extract JSON payload
        payload_start = 18
        payload = packet[payload_start:payload_start + packet_data_length - 12]
        
        try:
            json_data = json.loads(payload.decode('utf-8'))
            return apid, msg_type, subtype, json_data
        except:
            return apid, msg_type, subtype, None
    
    def send_command(self, command_dict, packet_type=1, subtype=1):
        """Send command and receive response"""
        command_json = json.dumps(command_dict)
        packet = self.create_space_packet(command_json, packet_type, subtype)
        
        print(f"\n→ Sending: {command_dict}")
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Receive response
        response_data, _ = self.socket.recvfrom(4096)
        apid, msg_type, subtype, json_response = self.decode_space_packet(response_data)
        
        print(f"← Received: {json_response}")
        return apid, msg_type, subtype, json_response
    
    # ========================================================================
    # Test Cases
    # ========================================================================
    
    def test_01_heartbeat(self):
        """Test OBC heartbeat command"""
        print("\n" + "="*70)
        print("TEST: OBC Heartbeat")
        print("="*70)
        
        command = {"ObcHeartBeat": {"HeartBeat": 42}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=1)
        
        # Verify response
        self.assertIsNotNone(response)
        self.assertIn("PduHeartBeat", response)
        self.assertEqual(response["PduHeartBeat"]["HeartBeat"], 42)
        self.assertIn("PduState", response["PduHeartBeat"])
        
        print("✓ Heartbeat test passed")
    
    def test_02_get_pdu_status(self):
        """Test GetPduStatus command"""
        print("\n" + "="*70)
        print("TEST: Get PDU Status")
        print("="*70)
        
        command = {"GetPduStatus": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=25)
        
        # Verify response structure
        self.assertIsNotNone(response)
        self.assertIn("PduStatus", response)
        
        status = response["PduStatus"]
        self.assertIn("PduState", status)
        self.assertIn("ProtectionStatus", status)
        self.assertIn("PduMode", status)
        
        print(f"✓ PDU Status: State={status['PduState']}, Mode={status['PduMode']}")
    
    def test_03_get_unit_line_states(self):
        """Test GetUnitLineStates command"""
        print("\n" + "="*70)
        print("TEST: Get Unit Line States")
        print("="*70)
        
        command = {"GetUnitLineStates": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=129)
        
        # Verify response structure
        self.assertIsNotNone(response)
        self.assertIn("PduUnitLineStates", response)
        
        unit_lines = response["PduUnitLineStates"]
        expected_lines = [
            "HighPwHeaterEnSel", "LowPwHeaterEnSel", "ReactionWheelEnSel",
            "PropEnSel", "AvionicLoadEnSel", "HdrmEnSel",
            "IsolatedLdoEnSel", "IsolatedPwEnSel", "ThermAndFlybackEnSel"
        ]
        
        for line in expected_lines:
            self.assertIn(line, unit_lines)
        
        print(f"✓ Unit Line States retrieved: {len(expected_lines)} categories")
    
    def test_04_state_transition_to_operate(self):
        """Test PduGoOperate state transition"""
        print("\n" + "="*70)
        print("TEST: State Transition to Operate")
        print("="*70)
        
        # First, transition to Load state (required before Operate)
        command = {"PduGoLoad": {}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Receive acknowledgement
        response_data, _ = self.socket.recvfrom(4096)
        apid, msg_type, subtype, ack_response = self.decode_space_packet(response_data)
        
        print(f"← Load Ack: {ack_response}")
        
        # Now transition to Operate
        command = {"PduGoOperate": {}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Receive acknowledgement
        response_data, _ = self.socket.recvfrom(4096)
        apid, msg_type, subtype, ack_response = self.decode_space_packet(response_data)
        
        # Verify acknowledgement
        self.assertIsNotNone(ack_response)
        self.assertIn("PduMsgAcknowledgement", ack_response)
        self.assertEqual(ack_response["PduMsgAcknowledgement"]["PduReturnCode"], 0)
        
        # Verify state changed
        time.sleep(0.5)
        command = {"GetPduStatus": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=25)
        
        self.assertEqual(response["PduStatus"]["PduState"], 2)  # Operate state
        
        print("✓ State transition to Operate successful")
    
    def test_05_set_unit_power_lines(self):
        """Test SetUnitPwLines command"""
        print("\n" + "="*70)
        print("TEST: Set Unit Power Lines")
        print("="*70)
        
        # Set high power heater lines
        command = {
            "SetUnitPwLines": {
                "LogicUnitId": 0,  # HighPwHeaterEnSel
                "Parameters": 0x0003  # Enable first two lines
            }
        }
        
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Receive acknowledgement
        response_data, _ = self.socket.recvfrom(4096)
        apid, msg_type, subtype, ack_response = self.decode_space_packet(response_data)
        
        print(f"← Set Ack: {ack_response}")
        
        # Verify lines were set
        time.sleep(0.5)
        command = {"GetUnitLineStates": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=129)
        
        self.assertEqual(response["PduUnitLineStates"]["HighPwHeaterEnSel"], 0x0003)
        
        print("✓ Unit power lines set successfully")
    
    def test_06_get_converted_measurements(self):
        """Test GetConvertedMeasurements command"""
        print("\n" + "="*70)
        print("TEST: Get Converted Measurements")
        print("="*70)
        
        # First set some unit lines to get measurements
        command = {
            "SetUnitPwLines": {
                "LogicUnitId": 2,  # ReactionWheelEnSel
                "Parameters": 0x000F  # Enable all 4 reaction wheels
            }
        }
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Wait for ack
        self.socket.recvfrom(4096)
        time.sleep(0.5)
        
        # Get measurements
        command = {
            "GetConvertedMeasurements": {
                "LogicUnitId": 2  # ReactionWheelEnSel
            }
        }
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=131)
        
        # Verify response
        self.assertIsNotNone(response)
        self.assertIn("PduConvertedMeasurements", response)
        
        measurements = response["PduConvertedMeasurements"]
        self.assertIn("ReactionWheelAdcSel", measurements)
        
        # Should have 4 measurements (one per reaction wheel)
        rw_measurements = measurements["ReactionWheelAdcSel"]
        self.assertEqual(len(rw_measurements), 4)
        
        # Each measurement should be around 5A (nominal current)
        for measurement in rw_measurements:
            self.assertGreater(measurement, 4.0)
            self.assertLess(measurement, 6.0)
        
        print(f"✓ Converted measurements: {rw_measurements}")
    
    def test_07_state_transition_to_safe(self):
        """Test PduGoSafe state transition"""
        print("\n" + "="*70)
        print("TEST: State Transition to Safe")
        print("="*70)
        
        # Ensure we're in Operate state first
        command = {"PduGoOperate": {}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        self.socket.recvfrom(4096)
        time.sleep(0.5)
        
        # Transition to Safe
        command = {"PduGoSafe": {}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Receive acknowledgement
        response_data, _ = self.socket.recvfrom(4096)
        apid, msg_type, subtype, ack_response = self.decode_space_packet(response_data)
        
        # Verify acknowledgement
        self.assertIsNotNone(ack_response)
        self.assertIn("PduMsgAcknowledgement", ack_response)
        self.assertEqual(ack_response["PduMsgAcknowledgement"]["PduReturnCode"], 0)
        
        # Verify state changed
        time.sleep(0.5)
        command = {"GetPduStatus": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=25)
        
        self.assertEqual(response["PduStatus"]["PduState"], 3)  # Safe state
        
        print("✓ State transition to Safe successful")
    
    def test_08_reset_unit_power_lines(self):
        """Test ResetUnitPwLines command"""
        print("\n" + "="*70)
        print("TEST: Reset Unit Power Lines")
        print("="*70)
        
        # First set some lines
        command = {
            "SetUnitPwLines": {
                "LogicUnitId": 1,  # LowPwHeaterEnSel
                "Parameters": 0x00FF
            }
        }
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        self.socket.recvfrom(4096)
        time.sleep(0.5)
        
        # Reset specific lines
        command = {
            "ResetUnitPwLines": {
                "LogicUnitId": 1,  # LowPwHeaterEnSel
                "Parameters": 0x000F  # Reset first 4 lines
            }
        }
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        self.socket.recvfrom(4096)
        time.sleep(0.5)
        
        # Verify lines were reset
        command = {"GetUnitLineStates": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=129)
        
        # Should be 0x00F0 (first 4 bits reset, last 4 still set)
        self.assertEqual(response["PduUnitLineStates"]["LowPwHeaterEnSel"], 0x000F)
        
        print("✓ Unit power lines reset successfully")
    
    def test_09_multiple_commands_sequence(self):
        """Test sequence of multiple commands"""
        print("\n" + "="*70)
        print("TEST: Multiple Commands Sequence")
        print("="*70)
        
        # 1. Get initial status
        command = {"GetPduStatus": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=25)
        initial_state = response["PduStatus"]["PduState"]
        print(f"  Initial state: {initial_state}")
        
        # 2. Set unit lines
        command = {"SetUnitPwLines": {"LogicUnitId": 3, "Parameters": 0x0003}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        self.socket.recvfrom(4096)
        time.sleep(0.3)
        
        # 3. Get unit line states
        command = {"GetUnitLineStates": {}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=129)
        self.assertEqual(response["PduUnitLineStates"]["PropEnSel"], 0x0003)
        print(f"  PropEnSel set to: 0x{response['PduUnitLineStates']['PropEnSel']:04X}")
        
        # 4. Get measurements
        command = {"GetConvertedMeasurements": {"LogicUnitId": 3}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=131)
        measurements = response["PduConvertedMeasurements"]["PropAdcSel"]
        print(f"  Prop measurements: {measurements}")
        
        # 5. Send heartbeat
        command = {"ObcHeartBeat": {"HeartBeat": 100}}
        apid, msg_type, subtype, response = self.send_command(command, packet_type=3, subtype=1)
        self.assertEqual(response["PduHeartBeat"]["HeartBeat"], 100)
        print(f"  Heartbeat: {response['PduHeartBeat']['HeartBeat']}")
        
        print("✓ Multiple commands sequence completed successfully")
    
    def test_10_invalid_state_transition(self):
        """Test invalid state transition (should be rejected)"""
        print("\n" + "="*70)
        print("TEST: Invalid State Transition")
        print("="*70)
        
        # Try to go to Maintenance from Boot state (invalid)
        # First ensure we're in Boot state
        command = {"PduGoBoot": {}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        try:
            self.socket.recvfrom(4096)
        except:
            pass
        
        time.sleep(0.5)
        
        # Try invalid transition
        command = {"PduGoMaintenance": {}}
        packet = self.create_space_packet(json.dumps(command), packet_type=1, subtype=1)
        self.socket.sendto(packet, (TEST_IP, TEST_PORT))
        
        # Receive acknowledgement
        response_data, _ = self.socket.recvfrom(4096)
        apid, msg_type, subtype, ack_response = self.decode_space_packet(response_data)
        
        # Should receive error acknowledgement
        self.assertIsNotNone(ack_response)
        self.assertIn("PduMsgAcknowledgement", ack_response)
        self.assertEqual(ack_response["PduMsgAcknowledgement"]["PduReturnCode"], 1)  # Error
        
        print("✓ Invalid state transition correctly rejected")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
