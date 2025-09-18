@echo off
title Offline-Service
color 02
cd /d %~dp0
set Path=jre\\bin;%PATH%
java -Xmx256m -Xms256m ^
	-cp ./jre/lib ^
	-Dspring.profiles.active=uat ^
	-DappKey=offline-trade-client-v2 ^
	-jar trade-wrap-0.0.4-SNAPSHOT.jar %1 %2
