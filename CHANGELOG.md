# Yumi Sugoi Changelog

## [v1.2.1] - 2025-05-23
### Added
- Persistent lockdown: Yumi now remembers which channel(s) are locked down in each server, even after a bot restart.
- Lockdown status is saved to `datasets/lockdown_channels.json` and restored on startup.

### Fixed
- Minor bug fixes and reliability improvements for lockdown and changelog posting.

## [v1.2.0] - 2025-05-22
### Added
- Per-user, per-channel context logic: Yumi now keeps conversation context separate for each user in servers.
- Changelog auto-posting: Only new changelog entries are posted to the changelog channel (ID: 1375129643925114973) using `!yumi_post_changelog`.
- `CHANGELOG.md` file for tracking all updates and fixes.
- Improved admin tools: lockdown, unlock, purge, say, and admin help commands.
- Lockdown now means Yumi only replies in the specified channel, but everyone can talk.
- Persona mode display and feedback improvements.

### Changed
- 'Normal' mode is now a friendly, caring AI companion (not flirty by default).
- Updated README.md for clarity and new features.

### Fixed
- Commands now work in all channels, even when lockdown is active.
- Yumi no longer mixes up user prompts in servers.
- Lockdown feedback and error handling improved.

## [v1.1.0] - 2024-12-10
### Added
- Image captioning with BLIP.
- Web search fallback for unknown questions.
- Persistent per-user name memory.
- Rotating Discord status and random DM reminders.

## [v1.0.0] - 2024-06-01
### Added
- Initial release: Multi-persona Discord AI chatbot with OpenAI support, self-learning Q&A, and basic admin tools.
