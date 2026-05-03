/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Simon Beckett
 * License: AGPLv3
 */
$(function() {
 
    ko.extenders.defaultIfNull = function(target, defaultValue) {
        var result = ko.computed({
            read: target,
            write: function(newValue) {
                if (!newValue) {
                    target(defaultValue);
                } else {
                    target(newValue);
                }
            }
        });
    
        result(target());
    
        return result;
    };

    function OctohueViewModel(parameters) {
        var self = this;
  
        self.settingsViewModel = parameters[0];
        self.selectedEvent = ko.observable();
        self.ownSettings = {};
        self.statusDict = [];
        self.hueLamps = ko.observableArray([]);
        self.huePlugs = ko.observableArray([]);

        self.addNewStatus = function () {
            var statusObj = {
                event: ko.observable(''),
                colour: ko.observable(''),
                brightness: ko.observable('').extend({ defaultIfNull: "255" }),
                delay: ko.observable('').extend({ defaultIfNull: "0" }),
                turnoff: ko.observable(false),
                flash: ko.observable(false),
                ct: ko.observable(0)
            };
            self.ownSettings.statusDict.push(statusObj);
        };

        self.bridgediscovery = function() {
            var search_button = this
		    search_button.innerHTML = '<i class="fa fa-search"></i> Searching...';
		    search_button.disabled = true;
		    //document.getElementById("huebridge_searchstatus").style.display = "none";
		    //document.getElementById("huebridge_found").style.display = "none";
            OctoPrint.simpleApiCommand("octohue", "bridge", {"discover": "true"}, {}).done(function(response) {
				search_button.innerHTML = '<i class="fa fa-search"></i> Search my bridge';
				search_button.disabled = false;
				if(response[0] && response[0].internalipaddress){
                    bridgeaddr = response[0].internalipaddress;
					document.getElementById("huebridge_searchstatus").classList.remove("inactiveconfig");
					document.getElementById("huebridge_searchstatus").innerHTML = "<font color='green'>Brige found (<i>"+ response[0].internalipaddress+ "</i>) !</font>";
					document.getElementById("huebridge_found").classList.remove("inactiveconfig");
				} else {
					document.getElementById("huebridge_searchstatus").classList.remove("inactiveconfig");
					document.getElementById("huebridge_searchstatus").innerHTML = "<font color='red'>No bridge found. Check your network and try again.</font>";
				}
			});
        };

        self.bridgepair = function() {
            var bridgebutton = document.getElementById("huebridge_pairingbutton");
		    bridgebutton.innerHTML = '<i class="fa fa-link"></i> Pairing...';
		    bridgebutton.disabled = true;
		    
            var pairing_try_count = 0;
		    var text_pairing_count = document.getElementById("huebridge_pairingreties");
		    text_pairing_count.innerHTML = "Try count: " + pairing_try_count + "/30";
		    document.getElementById("huebridge_startsearch").disabled = true;
		    var interval_pairing = setInterval(function() {
			pairing_try_count += 1;
			text_pairing_count.innerHTML = "Try count: " + pairing_try_count + "/30";
            
            OctoPrint.simpleApiCommand("octohue", "bridge", {"pair": "true", "bridgeaddr":bridgeaddr}, {}).done(function(response) {
				if(response[0].response == "success")
				{
                    clearInterval(interval_pairing);
                    self.ownSettings.bridgeaddr(response[0].bridgeaddr);
                    self.ownSettings.husername(response[0].husername);
                    document.getElementById("huebridgestatus").style.backgroundColor = "green";
                    document.getElementById("huebridgestatus").innerHTML = "Paired";
					text_pairing_count.innerHTML = "<font color='green'><strong>Bridge paired successfully!</strong> Click the button below to select your light, or click Save to continue later.</font>";
                    document.getElementById("huebridge_paired_actions").classList.remove("inactiveconfig");
				}
			})

			if(pairing_try_count == 30)
			{
				clearInterval(interval_pairing);
				bridgebutton.innerHTML = '<i class="fa fa-link"></i> Start Pairing';
				bridgebutton.disabled = false;
				text_pairing_count.innerHTML = "<font color='red'>Unable to pair. Please try again</font>";
				document.getElementById("huebridge_startsearch").disabled = false;
			}
		}, 1000);
        };
    
        self.fetchAllLamps = function() {
            self.getDevices().then(function(lights) {
                var nonPlugs = (lights || [])
                    .filter(function(d) { return d.archetype !== "plug"; })
                    .map(function(d) { return {id: d.id, name: d.name, type: "light"}; });
                self.getGroups().then(function(groups) {
                    var groupItems = (groups || [])
                        .map(function(g) { return {id: g.id, name: g.name + " (Group)", type: "group"}; });
                    self.hueLamps(nonPlugs.concat(groupItems));
                });
            });
        };

        self.goToLights = function() {
            document.getElementById("huebridge_paired_actions").classList.add("inactiveconfig");
            self.getDevices("plug").then(function(devices) { self.huePlugs(devices); });
            self.fetchAllLamps();
            $('#octohue_tabs a[href="#octohue_settings_lights"]').tab('show');
        };

        self.getbridgestatus = function() {
            OctoPrint.simpleApiCommand("octohue", "bridge", {"getstatus": "true"}, {}).done(function(response) {
                if (response.bridgestatus === "configured") {
                    document.getElementById("huebridgestatus").style.backgroundColor = "green";
                    document.getElementById("huebridgestatus").innerHTML = "Configured";
                    document.getElementById("huebridge_unconfigured").classList.add("inactiveconfig");
                    document.getElementById("huebridge_configured").classList.remove("inactiveconfig");
                } else if (response.bridgestatus === "unauthed") {
                    document.getElementById("huebridgestatus").style.backgroundColor = "orange";
                    document.getElementById("huebridgestatus").innerHTML = "Address set, not paired";
                    document.getElementById("huebridge_unconfigured").classList.remove("inactiveconfig");
                    document.getElementById("huebridge_configured").classList.add("inactiveconfig");
                } else {
                    document.getElementById("huebridge_configured").classList.add("inactiveconfig");
                    document.getElementById("huebridge_unconfigured").classList.remove("inactiveconfig");
                }
            });
        };

        self.getDevices = function (archetype) {
            var payload = archetype !== undefined ? {"archetype": archetype} : {};
            return OctoPrint.simpleApiCommand("octohue", "getdevices", payload, {})
                .then(response => response.devices);
        };

        self.getGroups = function () {
            return OctoPrint.simpleApiCommand("octohue", "getgroups", {}, {})
                .then(response => response.groups);
        };

        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.ownSettings = self.settings.plugins.octohue;
            self.statusDict = self.ownSettings.statusDict;

            // Ensure flash and ct are ko.observables on every loaded statusDict item
            // (items saved before these features were added won't have them)
            ko.utils.arrayForEach(self.statusDict(), function(item) {
                if (!ko.isObservable(item.flash)) {
                    item.flash = ko.observable(item.flash || false);
                }
                if (!ko.isObservable(item.ct)) {
                    item.ct = ko.observable(item.ct || 0);
                }
            });

            // Auto-set lampisgroup when the user picks a device from the combined
            // dropdown, so the backend still knows which API endpoint to use.
            self.ownSettings.lampid.subscribe(function(newId) {
                var lamp = ko.utils.arrayFirst(self.hueLamps(), function(l) { return l.id === newId; });
                if (lamp) {
                    self.ownSettings.lampisgroup(lamp.type === "group");
                }
            });

            // When the provider dropdown changes to Hue, fetch bridge status and
            // devices immediately so the pairing flow is ready without reopening settings.
            self.ownSettings.provider.subscribe(function(newProvider) {
                if (newProvider === "hue") {
                    self.getbridgestatus();
                    self.getDevices("plug").then(function(devices) { self.huePlugs(devices); });
                }
                self.fetchAllLamps();
            });
        };

        self.onSettingsShown = function () {
            if (self.ownSettings.provider() === "hue") {
                self.getbridgestatus();
                self.getDevices("plug").then(function(devices) { self.huePlugs(devices); });
            }
            self.fetchAllLamps();
        };

        self.removeStatus = function (data) {
            self.ownSettings.statusDict.remove(
                data
            );
        };

        self.setSwitchOff = function(status) {
            status.turnoff(!status.turnoff());
        };

        self.setFlash = function(status) {
            status.flash(!status.flash());
        };

        self.statusDetails = function (data) {
            if (data === false) {
                return {
                    event: ko.observable(""),
                    colour: ko.observable(""),
                    brightness: ko.observable(""),
                    delay: ko.observable(""),
                    turnoff: ko.observable(false),
                    flash: ko.observable(false),
                    ct: ko.observable(0)
                };

            } else {
                if (!data.hasOwnProperty("turnoff")) {
                    data["turnoff"] = ko.observable(true);
                }
                if (!data.hasOwnProperty("flash")) {
                    data["flash"] = ko.observable(false);
                }
                if (!data.hasOwnProperty("ct")) {
                    data["ct"] = ko.observable(0);
                }
                return data;
            }
        };

        self.toggleCtMode = function(status) {
            if (status.ct()) {
                status.ct(0);
            } else {
                status.ct(370); // default ~2700K warm white
            }
        };

        self.toggleToggleCtMode = function() {
            if (self.ownSettings.togglect()) {
                self.ownSettings.togglect(0);
            } else {
                self.ownSettings.togglect(370);
            }
        };

        self.togglehue = function() {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {}, {});
        };
        
        self.togglepower = function(data) {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {"deviceid": self.ownSettings.plugid()}, {});
        };


    };

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: OctohueViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_octohue", "#navbar_plugin_octohue"]
    })
})
