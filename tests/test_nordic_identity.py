"""Regression tests for the Nordic family's CID/MID read (#30).

Three models - X2A Wireless, Xlite V3, X2 V2 Mini - ship on the same two
PIDs, and command 0x01 is how Fusion tells them apart ("CheckPsd" in its own
log).  The request carries a 4-byte nonce; the answer carries the pair after
the nonce it transforms.  Bytes from two usbmon captures of Fusion starting
against an Xlite V3, contributed by @bluesceada.
"""

import unittest

from pulsar_mouse.drivers.nordic import CMD_HANDSHAKE, PulsarNordic

# The second capture, byte for byte.
FUSION_REQUEST = bytes.fromhex('08010000000829320a550000000000008a')
FUSION_REPLY = bytes.fromhex('0801000000086175737d0607020000006f')


def scripted(reply=FUSION_REPLY):
    """A Nordic mouse whose transport answers with `reply`."""

    class Scripted(PulsarNordic):
        def __init__(self):
            super().__init__()
            self._fd = 17           # pretend hidraw is open
            self.sent = []

        def _send(self, packet):
            self.sent.append(bytes(packet))

        def _recv(self, timeout_ms=2000):
            return reply

    return Scripted()


class ModelIdsTests(unittest.TestCase):
    def test_the_pair_comes_from_the_two_bytes_after_the_nonce(self):
        self.assertEqual(scripted().get_model_ids(), (6, 7))

    def test_the_request_is_shaped_like_fusion_s(self):
        mouse = scripted()
        mouse.get_model_ids()
        sent = mouse.sent[-1]
        self.assertEqual(sent[:6], FUSION_REQUEST[:6])   # cmd 0x01, length 8
        self.assertEqual(sent[10:16], bytes(6))
        self.assertEqual(sent[16], PulsarNordic._checksum(*sent[:16]))

    def test_the_nonce_is_not_a_constant(self):
        nonces = set()
        for _ in range(8):
            mouse = scripted()
            mouse.get_model_ids()
            nonces.add(bytes(mouse.sent[-1][6:10]))
        self.assertGreater(len(nonces), 1)

    def test_the_answer_is_matched_to_the_command(self):
        # _command() rejects anything that is not this command's reply, so a
        # mouse event landing mid-read cannot be taken for the pair.
        mouse = scripted(reply=bytes.fromhex(
            '080a00000001000000000000000000003e'))      # an 0x0a event
        with self.assertRaises(RuntimeError):
            mouse.get_model_ids()

    def test_it_asks_the_command_fusion_asks(self):
        self.assertEqual(CMD_HANDSHAKE, 0x01)


if __name__ == '__main__':
    unittest.main()
