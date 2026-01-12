# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-10

### Added
- Voicemail sync from Placetel API with automatic audio download
- Speech-to-text transcription via ElevenLabs API
- AI-powered transcript correction and summarization via OpenRouter (Gemini)
- AI classification: sentiment, emotion, category, and urgency detection
- Background scheduler (APScheduler) for automatic processing pipeline
- Settings system with database-backed configuration
- Admin UI for managing settings and triggering manual sync
- REST API for voicemails, transcription, summarization, and settings
- React frontend with voicemail list, detail view, and audio playback
- Docker Compose setup with PostgreSQL 18

### Changed
- Renamed project from "Placetel Voicemail" to "Phone" (sgos.phone)
- Reset database migrations to single clean initial schema

[1.0.0]: https://github.com/sonnenglas/sgos-phone/releases/tag/v1.0.0
