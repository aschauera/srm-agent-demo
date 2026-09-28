# SRM Agent Demo

This repository contains a self-contained Supplier Risk Management demo built around Dataverse,
Copilot Studio, and a model-driven app.

Start with [AGENTS.md](AGENTS.md) for agent and contributor guidance. The approved architecture and
work breakdown are in [the implementation plan](docs/planning/implementation-plan.md); the source
presentation text and traceability rules are in [the requirements guide](docs/requirements/README.md).

The first implementation slice is the [Dataverse data model](docs/02-dataverse-data-model.md), with
fictional seed records for all planned mock connector tables. The intended Power Platform target is
DemoPRE, using the unmanaged `SRMAgentDemo` solution and the dedicated `mag` publisher.

