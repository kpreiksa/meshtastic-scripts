import sys
import os
import unittest
import datetime
from freezegun import freeze_time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
from util import uptime_str, get_current_time_str, time_from_ts, time_str_from_dt, convert_secs_to_pretty, DiscordInteractionInfo

class TestUtilFunctions(unittest.TestCase):
    def test_uptime_str(self):
        # Test with seconds only
        self.assertEqual(uptime_str(45), '45 seconds.')

        # Test with minutes and seconds
        self.assertEqual(uptime_str(125), '2 minutes, 5 seconds.')

        # Test with hours, minutes, and seconds
        self.assertEqual(uptime_str(3725), '1 hours, 2 minutes, 5 seconds.')

        # Test with days, hours, minutes, and seconds
        self.assertEqual(uptime_str(90061), '1 days, 1 hours, 1 minutes, 1 seconds.')

        # Test with None
        self.assertEqual(uptime_str(None), 'Not Available')

    @freeze_time("2025-08-10 12:34:56", tz_offset=0)
    def test_get_current_time_str(self):
        expected = "10 August 2025 12:34:56 PM"
        self.assertEqual(get_current_time_str(), expected)

    def test_time_from_ts(self):
        # Test with a specific timestamp
        ts = 1691676896  # Thu Aug 10 2023 12:34:56 GMT+0000
        expected = "10 August 2023 12:34:56 PM"
        self.assertEqual(time_from_ts(ts), expected)

    def test_time_str_from_dt(self):
        # Test with a specific datetime
        dt = datetime.datetime(2023, 8, 10, 12, 34, 56)
        expected = "10 August 2023 12:34:56 PM"
        self.assertEqual(time_str_from_dt(dt), expected)

    def test_convert_secs_to_pretty(self):
        # This should behave the same as uptime_str
        self.assertEqual(convert_secs_to_pretty(45), '45 seconds.')
        self.assertEqual(convert_secs_to_pretty(None), 'Not Available')

    def test_discord_interaction_info(self):
        interaction = DiscordInteractionInfo(
            guild_id="12345",
            channel_id="67890",
            message_id="13579",
            user_id="24680",
            user_display_name="TestUser",
            user_global_name="Global TestUser",
            user_name="test_user",
            user_mention="@test_user"
        )

        self.assertEqual(interaction.guild_id, "12345")
        self.assertEqual(interaction.channel_id, "67890")
        self.assertEqual(interaction.message_id, "13579")
        self.assertEqual(interaction.user_id, "24680")
        self.assertEqual(interaction.user_display_name, "TestUser")
        self.assertEqual(interaction.user_global_name, "Global TestUser")
        self.assertEqual(interaction.user_name, "test_user")
        self.assertEqual(interaction.user_mention, "@test_user")

if __name__ == '__main__':
    unittest.main()
