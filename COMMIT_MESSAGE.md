# Yumi Sugoi v1.4.1 - Lockdown Feature and Persistence Fix

## Issues Fixed
1. Fixed an issue where the `!yumi_lockdown` command was changing channel permissions to prevent everyone from speaking in the channel, rather than just restricting Yumi to respond only in the locked channel.
2. Fixed an issue where lockdown settings didn't persist after bot restart due to a duplicate initialization of the LOCKED_CHANNELS variable.

## Changes Made
- Removed channel permission modifications from the `yumi_lockdown` command
- Updated the `yumi_unlock` function to no longer modify channel permissions
- Fixed duplicate declaration of LOCKED_CHANNELS that was overwriting the loaded settings
- Added explicit loading of lockdown settings in the `run()` function with debug logs
- Updated help text and documentation to be more accurate about what lockdown does
- Added clarification in admin tools description

## Expected Behavior
- When using `!yumi_lockdown`, Yumi will now only respond in the channel where lockdown was activated, but all users will still be able to speak in all channels. This is consistent with the intended behavior as stated in the changelog (v1.2.0): "Lockdown now means Yumi only replies in the specified channel, but everyone can talk."
- Lockdown settings will now persist when the bot is restarted, ensuring Yumi remains locked to the specified channel(s).

## Affected Files
- bot_core/main.py
- CHANGELOG.md
