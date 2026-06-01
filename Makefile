.PHONY: help install-launchd uninstall-launchd reload-launchd dev-dashboard dev-worker

help:
	@echo "Curated Curiosities — Makefile targets"
	@echo ""
	@echo "  install-launchd     Install + start the worker and analyst launchd jobs"
	@echo "  uninstall-launchd   Stop and remove the launchd jobs"
	@echo "  reload-launchd      Reinstall after editing the plists"
	@echo "  dev-dashboard       Run the Next.js dashboard locally"
	@echo "  dev-worker          Run the Python worker in the foreground (no launchd)"

WORKER_PLIST := $(HOME)/Library/LaunchAgents/com.curatedcuriosities.worker.plist
ANALYST_PLIST := $(HOME)/Library/LaunchAgents/com.curatedcuriosities.analyst.plist
UID := $(shell id -u)

install-launchd:
	@mkdir -p $(HOME)/Library/LaunchAgents $(HOME)/Library/Logs
	cp infra/launchd/curated.worker.plist $(WORKER_PLIST)
	cp infra/launchd/curated.analyst.plist $(ANALYST_PLIST)
	plutil -lint $(WORKER_PLIST)
	plutil -lint $(ANALYST_PLIST)
	-launchctl bootout gui/$(UID) $(WORKER_PLIST) 2>/dev/null
	-launchctl bootout gui/$(UID) $(ANALYST_PLIST) 2>/dev/null
	launchctl bootstrap gui/$(UID) $(WORKER_PLIST)
	launchctl bootstrap gui/$(UID) $(ANALYST_PLIST)
	@echo ""
	@echo "Installed. Check status with:"
	@echo "  launchctl list | grep curatedcuriosities"

uninstall-launchd:
	-launchctl bootout gui/$(UID) $(WORKER_PLIST)
	-launchctl bootout gui/$(UID) $(ANALYST_PLIST)
	rm -f $(WORKER_PLIST) $(ANALYST_PLIST)

reload-launchd: uninstall-launchd install-launchd

dev-dashboard:
	cd dashboard && pnpm dev

dev-worker:
	python3 worker/cli.py daemon
