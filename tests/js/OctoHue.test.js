/**
 * Unit tests for OctoHue.js (KnockoutJS viewmodel).
 *
 * Strategy
 * --------
 * The source file is wrapped in `$(function(){ … })`, so we mock jQuery's `$`
 * to call its argument synchronously.  We then provide lightweight mocks for
 * KnockoutJS, the OctoPrint simple-API helper, and DOM elements so the
 * viewmodel constructor and all its methods can be exercised without a browser.
 *
 * After the file is eval'd, `OCTOPRINT_VIEWMODELS[0].construct` holds the
 * `OctohueViewModel` constructor.  Each test creates a fresh instance via
 * `makeViewModel()`.
 */

const fs   = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// A synchronous thenable that supports both Promise-style .then()/.catch()
// and jQuery-style .done()/.fail(), so test assertions can be synchronous.
// ---------------------------------------------------------------------------
class SyncResult {
  constructor(value, isError = false) {
    this._value   = value;
    this._isError = isError;
  }
  then(onFulfilled, onRejected) {
    if (this._isError) {
      return new SyncResult(onRejected ? onRejected(this._value) : this._value, true);
    }
    return new SyncResult(onFulfilled ? onFulfilled(this._value) : this._value);
  }
  catch(onRejected) {
    if (this._isError) {
      return new SyncResult(onRejected ? onRejected(this._value) : this._value);
    }
    return this;
  }
  done(cb) { if (!this._isError && cb) cb(this._value); return this; }
  fail(cb) { if (this._isError  && cb) cb(this._value); return this; }
}

// ---------------------------------------------------------------------------
// KnockoutJS mock
// ---------------------------------------------------------------------------

/** Create a simple observable that acts as a getter/setter function. */
function makeObservable(initial) {
  let _val = initial;
  const obs = jest.fn().mockImplementation((newVal) => {
    if (newVal !== undefined) _val = newVal;
    return _val;
  });
  obs._isObservable = true;
  obs.extend = jest.fn().mockImplementation(() => obs);
  return obs;
}

const ko = {
  observable: jest.fn().mockImplementation(makeObservable),

  computed: jest.fn().mockImplementation(({ read, write }) => {
    const comp = jest.fn().mockImplementation((newVal) => {
      if (newVal !== undefined && write) write(newVal);
      return read ? read() : undefined;
    });
    comp.extend = jest.fn().mockReturnValue(comp);
    return comp;
  }),

  observableArray: jest.fn().mockImplementation((initial) => {
    const arr = [...(initial || [])];
    const obs = jest.fn().mockImplementation(() => arr);
    obs._isObservable = true;
    obs.push   = jest.fn().mockImplementation((item) => arr.push(item));
    obs.remove = jest.fn().mockImplementation((item) => {
      const idx = arr.indexOf(item);
      if (idx !== -1) arr.splice(idx, 1);
    });
    return obs;
  }),

  isObservable: jest.fn().mockImplementation((val) =>
    typeof val === "function" && val._isObservable === true
  ),

  utils: {
    arrayForEach: jest.fn().mockImplementation((arr, cb) => {
      const items = typeof arr === "function" ? arr() : arr;
      (items || []).forEach(cb);
    }),
  },

  extenders: {},
};

// ---------------------------------------------------------------------------
// OctoPrint API mock
// ---------------------------------------------------------------------------
const OctoPrint = {
  simpleApiCommand: jest.fn().mockImplementation(() =>
    new SyncResult({ devices: [], bridgestatus: "unconfigured" })
  ),
};

// ---------------------------------------------------------------------------
// DOM mock helpers
// ---------------------------------------------------------------------------
function makeDomElement(id) {
  return {
    id,
    innerHTML: "",
    disabled: false,
    style: { backgroundColor: "" },
    classList: {
      _classes: new Set(),
      add:    jest.fn().mockImplementation(function(c) { this._classes.add(c); }),
      remove: jest.fn().mockImplementation(function(c) { this._classes.delete(c); }),
      contains: jest.fn().mockImplementation(function(c) { return this._classes.has(c); }),
    },
    value: "",
  };
}

// ---------------------------------------------------------------------------
// Load source file
// ---------------------------------------------------------------------------
let ViewModelConstructor;

beforeAll(() => {
  const domElements = {};

  // Globals the source file expects
  global.$ = jest.fn().mockImplementation((arg) => {
    if (typeof arg === "function") arg();
    return { tab: jest.fn() };
  });
  global.ko = ko;
  global.OctoPrint = OctoPrint;
  global.OCTOPRINT_VIEWMODELS = [];
  global.document = {
    getElementById: jest.fn().mockImplementation((id) => {
      if (!domElements[id]) domElements[id] = makeDomElement(id);
      return domElements[id];
    }),
  };

  const src = fs.readFileSync(
    path.join(__dirname, "../../octoprint_octohue/static/js/OctoHue.js"),
    "utf8"
  );
  // eslint-disable-next-line no-eval
  eval(src);

  ViewModelConstructor = global.OCTOPRINT_VIEWMODELS[0].construct;
});

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeStatusDictMock(initialItems = []) {
  const items = [...initialItems];
  // Must be callable: onBeforeBinding calls self.statusDict() to get the array
  const mock = jest.fn().mockImplementation(() => items);
  mock._isObservable = true;
  mock.push   = jest.fn().mockImplementation((item) => items.push(item));
  mock.remove = jest.fn().mockImplementation((item) => {
    const idx = items.indexOf(item);
    if (idx !== -1) items.splice(idx, 1);
  });
  mock._items = items;
  return mock;
}

function makeViewModel(pluginSettingsOverrides = {}) {
  const statusDict = makeStatusDictMock();
  const pluginSettings = {
    statusDict,
    plugid: makeObservable("2"),
    lampisgroup: makeObservable(false),
    bridgeaddr: makeObservable(""),
    husername: makeObservable(""),
    ...pluginSettingsOverrides,
  };

  const settingsViewModel = {
    settings: {
      plugins: {
        octohue: pluginSettings,
      },
    },
  };

  const vm = new ViewModelConstructor([settingsViewModel]);
  // Simulate OctoPrint's binding lifecycle so ownSettings is populated.
  vm.onBeforeBinding();
  return vm;
}

// ---------------------------------------------------------------------------
// Reset mocks between tests
// ---------------------------------------------------------------------------
beforeEach(() => {
  ko.observable.mockClear();
  ko.computed.mockClear();
  OctoPrint.simpleApiCommand.mockClear();
  document.getElementById.mockClear();
  $.mockClear();
});

// ===========================================================================
// ko.extenders.defaultIfNull
// ===========================================================================

describe("ko.extenders.defaultIfNull", () => {
  // The extender is registered onto ko.extenders during file eval.
  let extender;

  beforeAll(() => {
    extender = ko.extenders.defaultIfNull;
  });

  test("extender is registered on ko.extenders", () => {
    expect(typeof extender).toBe("function");
  });

  test("write with falsy value uses the default", () => {
    const target = makeObservable("original");
    const extended = extender(target, "DEFAULT");
    extended(null);
    expect(target()).toBe("DEFAULT");
  });

  test("write with truthy value uses the supplied value", () => {
    const target = makeObservable("");
    const extended = extender(target, "DEFAULT");
    extended("hello");
    expect(target()).toBe("hello");
  });

  test("initial value is applied immediately", () => {
    const target = makeObservable("initial");
    extender(target, "DEFAULT");
    expect(target()).toBe("initial");
  });
});

// ===========================================================================
// Registration in OCTOPRINT_VIEWMODELS
// ===========================================================================

describe("OCTOPRINT_VIEWMODELS registration", () => {
  test("exactly one viewmodel is registered", () => {
    expect(global.OCTOPRINT_VIEWMODELS).toHaveLength(1);
  });

  test("registered viewmodel depends on settingsViewModel", () => {
    expect(global.OCTOPRINT_VIEWMODELS[0].dependencies).toContain(
      "settingsViewModel"
    );
  });

  test("registered viewmodel targets the settings and navbar elements", () => {
    const elements = global.OCTOPRINT_VIEWMODELS[0].elements;
    expect(elements).toContain("#settings_plugin_octohue");
    expect(elements).toContain("#navbar_plugin_octohue");
  });
});

// ===========================================================================
// addNewStatus
// ===========================================================================

describe("addNewStatus", () => {
  test("pushes a new entry onto statusDict", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    expect(vm.ownSettings.statusDict.push).toHaveBeenCalledTimes(1);
  });

  test("new entry has the correct observable fields", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const entry = vm.ownSettings.statusDict.push.mock.calls[0][0];
    expect(typeof entry.event).toBe("function");        // observable
    expect(typeof entry.colour).toBe("function");       // observable
    expect(typeof entry.brightness).toBe("function");   // observable
    expect(typeof entry.delay).toBe("function");        // observable
    expect(typeof entry.turnoff).toBe("function");      // observable
  });

  test("brightness observable uses defaultIfNull with '255'", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const entry = vm.ownSettings.statusDict.push.mock.calls[0][0];
    // The .extend() call applies the defaultIfNull extender
    expect(entry.brightness.extend).toHaveBeenCalledWith({
      defaultIfNull: "255",
    });
  });

  test("delay observable uses defaultIfNull with '0'", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const entry = vm.ownSettings.statusDict.push.mock.calls[0][0];
    expect(entry.delay.extend).toHaveBeenCalledWith({ defaultIfNull: "0" });
  });
});

// ===========================================================================
// removeStatus
// ===========================================================================

describe("removeStatus", () => {
  test("calls statusDict.remove with the supplied data", () => {
    const vm = makeViewModel();
    const fakeItem = { event: makeObservable("PrintDone") };
    vm.removeStatus(fakeItem);
    expect(vm.ownSettings.statusDict.remove).toHaveBeenCalledWith(fakeItem);
  });
});

// ===========================================================================
// setSwitchOff
// ===========================================================================

describe("setSwitchOff", () => {
  test("toggles turnoff from false to true", () => {
    const vm = makeViewModel();
    const status = { turnoff: makeObservable(false) };
    vm.setSwitchOff(status);
    expect(status.turnoff()).toBe(true);
  });

  test("toggles turnoff from true to false", () => {
    const vm = makeViewModel();
    const status = { turnoff: makeObservable(true) };
    vm.setSwitchOff(status);
    expect(status.turnoff()).toBe(false);
  });
});

// ===========================================================================
// statusDetails
// ===========================================================================

describe("statusDetails", () => {
  test("data=false returns a fresh object with empty observables", () => {
    const vm = makeViewModel();
    const result = vm.statusDetails(false);
    expect(typeof result.event).toBe("function");
    expect(typeof result.colour).toBe("function");
    expect(typeof result.brightness).toBe("function");
    expect(typeof result.delay).toBe("function");
    expect(typeof result.turnoff).toBe("function");
  });

  test("data=false returns turnoff defaulting to false", () => {
    const vm = makeViewModel();
    const result = vm.statusDetails(false);
    expect(result.turnoff()).toBe(false);
  });

  test("data with existing turnoff returns data unchanged", () => {
    const vm = makeViewModel();
    const existingTurnoff = makeObservable(true);
    const data = { turnoff: existingTurnoff, event: makeObservable("X") };
    const result = vm.statusDetails(data);
    expect(result.turnoff).toBe(existingTurnoff);
  });

  test("data without turnoff gets turnoff added as an observable", () => {
    const vm = makeViewModel();
    const data = { event: makeObservable("X") };
    const result = vm.statusDetails(data);
    expect(typeof result.turnoff).toBe("function");
    expect(result.turnoff()).toBe(true); // default inserted value
  });
});

// ===========================================================================
// togglehue
// ===========================================================================

describe("togglehue", () => {
  test("calls simpleApiCommand with togglehue and empty data", () => {
    const vm = makeViewModel();
    vm.togglehue();
    expect(OctoPrint.simpleApiCommand).toHaveBeenCalledWith(
      "octohue",
      "togglehue",
      {},
      {}
    );
  });
});

// ===========================================================================
// togglepower
// ===========================================================================

describe("togglepower", () => {
  test("calls simpleApiCommand with the plugid from settings", () => {
    const plugid = makeObservable("5");
    const vm = makeViewModel({ plugid });
    vm.togglepower();
    expect(OctoPrint.simpleApiCommand).toHaveBeenCalledWith(
      "octohue",
      "togglehue",
      { deviceid: "5" },
      {}
    );
  });
});

// ===========================================================================
// bridgepair
// ===========================================================================

describe("bridgepair", () => {
  beforeEach(() => { jest.useFakeTimers(); });
  afterEach(() => { jest.useRealTimers(); });

  function makePairVm(overrides = {}) {
    const vm = makeViewModel(overrides);
    vm.getbridgestatus = jest.fn();
    vm.getDevices = jest.fn(() => new SyncResult([]));
    vm.getGroups  = jest.fn(() => new SyncResult([]));
    return vm;
  }

  const SUCCESS_RESPONSE = new SyncResult([{
    response: "success", bridgeaddr: "10.0.0.1", husername: "new-key"
  }]);

  function runPairSuccess(vm) {
    // bridgepair reads the module-level `bridgeaddr` closure variable that is set
    // by bridgediscovery. Run discovery first so the variable is defined.
    OctoPrint.simpleApiCommand.mockReturnValueOnce(
      new SyncResult([{ internalipaddress: "192.168.1.100" }])
    );
    vm.bridgediscovery();
    OctoPrint.simpleApiCommand.mockReturnValueOnce(SUCCESS_RESPONSE);
    vm.bridgepair();
    jest.advanceTimersByTime(1000); // first interval tick → pair success
  }

  test("on success, updates bridgeaddr observable", () => {
    const bridgeaddr = makeObservable("");
    const vm = makePairVm({ bridgeaddr });
    runPairSuccess(vm);
    expect(bridgeaddr).toHaveBeenCalledWith("10.0.0.1");
  });

  test("on success, updates husername observable", () => {
    const husername = makeObservable("");
    const vm = makePairVm({ husername });
    runPairSuccess(vm);
    expect(husername).toHaveBeenCalledWith("new-key");
  });

  test("on success, calls getbridgestatus", () => {
    const vm = makePairVm();
    runPairSuccess(vm);
    expect(vm.getbridgestatus).toHaveBeenCalledTimes(1);
  });

  test("on success, reveals the Select light button", () => {
    const vm = makePairVm();
    runPairSuccess(vm);
    const actions = document.getElementById("huebridge_paired_actions");
    expect(actions.classList.remove).toHaveBeenCalledWith("inactiveconfig");
  });

  test("on success, does not immediately navigate to the Lights tab", () => {
    const vm = makePairVm();
    runPairSuccess(vm);
    expect($).not.toHaveBeenCalledWith('#octohue_tabs a[href="#octohue_settings_lights"]');
  });

  test("on error response, does not update observables or show button", () => {
    const bridgeaddr = makeObservable("");
    const vm = makePairVm({ bridgeaddr });
    // Clear call history so previous success tests don't pollute this assertion
    document.getElementById("huebridge_paired_actions").classList.remove.mockClear();
    OctoPrint.simpleApiCommand.mockReturnValueOnce(
      new SyncResult([{ internalipaddress: "192.168.1.100" }])
    );
    vm.bridgediscovery();
    OctoPrint.simpleApiCommand.mockReturnValueOnce(
      new SyncResult([{ response: "error" }])
    );
    vm.bridgepair();
    jest.advanceTimersByTime(1000); // one interval tick → error response → interval not cleared
    expect(bridgeaddr).not.toHaveBeenCalledWith(expect.anything());
    const actions = document.getElementById("huebridge_paired_actions");
    expect(actions.classList.remove).not.toHaveBeenCalledWith("inactiveconfig");
  });
});

// ===========================================================================
// goToLights
// ===========================================================================

describe("goToLights", () => {
  function makeLightsVm(overrides = {}) {
    const vm = makeViewModel(overrides);
    vm.getDevices = jest.fn(() => new SyncResult([]));
    vm.getGroups  = jest.fn(() => new SyncResult([]));
    return vm;
  }

  test("fetches lights and populates hueLamps when not a group", () => {
    const lamps = [{ id: "abc-1", name: "Desk Lamp" }];
    const vm = makeLightsVm();
    vm.getDevices = jest.fn(() => new SyncResult(lamps));
    vm.goToLights();
    expect(vm.hueLamps).toHaveBeenCalledWith(lamps);
  });

  test("fetches groups and populates hueLamps when lampisgroup is true", () => {
    const groups = [{ id: "gl-uuid-1", name: "Living Room" }];
    const vm = makeLightsVm({ lampisgroup: makeObservable(true) });
    vm.getGroups = jest.fn(() => new SyncResult(groups));
    vm.goToLights();
    expect(vm.getGroups).toHaveBeenCalled();
    expect(vm.hueLamps).toHaveBeenCalledWith(groups);
  });

  test("switches to the Lights tab", () => {
    const vm = makeLightsVm();
    vm.goToLights();
    expect($).toHaveBeenCalledWith('#octohue_tabs a[href="#octohue_settings_lights"]');
  });

  test("hides the Select light button", () => {
    const vm = makeLightsVm();
    vm.goToLights();
    const actions = document.getElementById("huebridge_paired_actions");
    expect(actions.classList.add).toHaveBeenCalledWith("inactiveconfig");
  });
});

// ===========================================================================
// getbridgestatus
// ===========================================================================

describe("getbridgestatus", () => {
  test("configured status sets badge to green and shows configured panel", () => {
    // Create vm first — its constructor calls getDevices() twice, which would
    // consume any mockReturnValueOnce set before construction.
    const vm = makeViewModel();
    OctoPrint.simpleApiCommand.mockReturnValueOnce(
      new SyncResult({ bridgestatus: "configured" })
    );
    vm.getbridgestatus();

    const badge = document.getElementById("huebridgestatus");
    expect(badge.style.backgroundColor).toBe("green");
    expect(badge.innerHTML).toBe("Configured");

    const unconfigured = document.getElementById("huebridge_unconfigured");
    expect(unconfigured.classList.add).toHaveBeenCalledWith("inactiveconfig");

    const configured = document.getElementById("huebridge_configured");
    expect(configured.classList.remove).toHaveBeenCalledWith("inactiveconfig");
  });

  test("unconfigured status shows unconfigured panel", () => {
    OctoPrint.simpleApiCommand.mockReturnValueOnce(
      new SyncResult({ bridgestatus: "unconfigured" })
    );
    const vm = makeViewModel();
    vm.getbridgestatus();

    const configured = document.getElementById("huebridge_configured");
    expect(configured.classList.add).toHaveBeenCalledWith("inactiveconfig");

    const unconfigured = document.getElementById("huebridge_unconfigured");
    expect(unconfigured.classList.remove).toHaveBeenCalledWith("inactiveconfig");
  });

  test("issues the correct API command", () => {
    const vm = makeViewModel();
    vm.getbridgestatus();
    expect(OctoPrint.simpleApiCommand).toHaveBeenCalledWith(
      "octohue",
      "bridge",
      { getstatus: "true" },
      {}
    );
  });
});

// ===========================================================================
// getDevices
// ===========================================================================

describe("getDevices", () => {
  test("calls simpleApiCommand with archetype when provided", () => {
    const vm = makeViewModel();
    vm.getDevices("plug");
    expect(OctoPrint.simpleApiCommand).toHaveBeenCalledWith(
      "octohue",
      "getdevices",
      { archetype: "plug" },
      {}
    );
  });

  test("calls simpleApiCommand without archetype when not provided", () => {
    const vm = makeViewModel();
    vm.getDevices(undefined);
    expect(OctoPrint.simpleApiCommand).toHaveBeenCalledWith(
      "octohue",
      "getdevices",
      { archetype: undefined },
      {}
    );
  });

  test("returns the devices array from the response", () => {
    const mockDevices = [{ id: "1", name: "Desk Lamp" }];
    // Create vm first so constructor calls don't consume our mock value.
    const vm = makeViewModel();
    OctoPrint.simpleApiCommand.mockReturnValueOnce(
      new SyncResult({ devices: mockDevices })
    );
    let received;
    vm.getDevices("tableShade").then((devices) => {
      received = devices;
    });
    expect(received).toEqual(mockDevices);
  });
});

// ===========================================================================
// onBeforeBinding / onSettingsShown
// ===========================================================================

describe("onBeforeBinding", () => {
  test("binds ownSettings to plugin settings namespace", () => {
    const vm = makeViewModel();
    vm.onBeforeBinding();
    expect(vm.ownSettings).toBe(
      vm.settingsViewModel.settings.plugins.octohue
    );
  });
});

describe("onSettingsShown", () => {
  test("calls getbridgestatus when settings panel is shown", () => {
    const vm = makeViewModel();
    vm.getbridgestatus = jest.fn();
    vm.getDevices = jest.fn(() => new SyncResult([]));
    vm.onSettingsShown();
    expect(vm.getbridgestatus).toHaveBeenCalledTimes(1);
  });

  test("populates huePlugs with devices returned for archetype plug", () => {
    const plugDevices = [{ id: "3", name: "Smart Plug", archetype: "plug" }];
    const lampDevices = [{ id: "1", name: "Desk Lamp", archetype: "tableShade" }];
    const vm = makeViewModel();
    vm.getbridgestatus = jest.fn();
    vm.getDevices = jest.fn()
      .mockImplementationOnce(() => new SyncResult(plugDevices))
      .mockImplementationOnce(() => new SyncResult(lampDevices));
    vm.onSettingsShown();
    expect(vm.huePlugs).toHaveBeenCalledWith(plugDevices);
  });

  test("populates hueLamps with lights when lampisgroup is false", () => {
    const plugDevices = [{ id: "3", name: "Smart Plug", archetype: "plug" }];
    const lampDevices = [{ id: "1", name: "Desk Lamp", archetype: "tableShade" }];
    const vm = makeViewModel({ lampisgroup: makeObservable(false) });
    vm.getbridgestatus = jest.fn();
    vm.getDevices = jest.fn()
      .mockImplementationOnce(() => new SyncResult(plugDevices))
      .mockImplementationOnce(() => new SyncResult(lampDevices));
    vm.onSettingsShown();
    expect(vm.hueLamps).toHaveBeenCalledWith(lampDevices);
  });

  test("populates hueLamps with groups when lampisgroup is true", () => {
    const plugDevices = [{ id: "3", name: "Smart Plug", archetype: "plug" }];
    const groupDevices = [{ id: "gl-uuid-1", name: "Living Room" }];
    const vm = makeViewModel({ lampisgroup: makeObservable(true) });
    vm.getbridgestatus = jest.fn();
    vm.getDevices = jest.fn(() => new SyncResult(plugDevices));
    vm.getGroups = jest.fn(() => new SyncResult(groupDevices));
    vm.onSettingsShown();
    expect(vm.hueLamps).toHaveBeenCalledWith(groupDevices);
    expect(vm.getGroups).toHaveBeenCalledTimes(1);
  });

  test("does not call getGroups when lampisgroup is false", () => {
    const vm = makeViewModel({ lampisgroup: makeObservable(false) });
    vm.getbridgestatus = jest.fn();
    vm.getDevices = jest.fn(() => new SyncResult([]));
    vm.getGroups = jest.fn(() => new SyncResult([]));
    vm.onSettingsShown();
    expect(vm.getGroups).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// setFlash
// ===========================================================================

describe("setFlash", () => {
  test("toggles flash from false to true", () => {
    const vm = makeViewModel();
    const status = { flash: makeObservable(false) };
    vm.setFlash(status);
    expect(status.flash()).toBe(true);
  });

  test("toggles flash from true to false", () => {
    const vm = makeViewModel();
    const status = { flash: makeObservable(true) };
    vm.setFlash(status);
    expect(status.flash()).toBe(false);
  });
});

// ===========================================================================
// addNewStatus — flash field
// ===========================================================================

describe("addNewStatus flash", () => {
  test("new status has flash as an observable", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const item = vm.ownSettings.statusDict._items[0];
    expect(typeof item.flash).toBe("function");
  });

  test("new status flash defaults to false", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const item = vm.ownSettings.statusDict._items[0];
    expect(item.flash()).toBe(false);
  });
});

// ===========================================================================
// addNewStatus — ct field
// ===========================================================================

describe("addNewStatus ct", () => {
  test("new status has ct as an observable", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const item = vm.ownSettings.statusDict._items[0];
    expect(typeof item.ct).toBe("function");
  });

  test("new status ct defaults to 0", () => {
    const vm = makeViewModel();
    vm.addNewStatus();
    const item = vm.ownSettings.statusDict._items[0];
    expect(item.ct()).toBe(0);
  });
});

// ===========================================================================
// statusDetails — flash field
// ===========================================================================

describe("statusDetails flash", () => {
  test("data=false returns flash observable defaulting to false", () => {
    const vm = makeViewModel();
    const result = vm.statusDetails(false);
    expect(typeof result.flash).toBe("function");
    expect(result.flash()).toBe(false);
  });

  test("data with existing flash observable is left unchanged", () => {
    const vm = makeViewModel();
    const existingFlash = makeObservable(true);
    const data = { turnoff: makeObservable(false), flash: existingFlash };
    const result = vm.statusDetails(data);
    expect(result.flash).toBe(existingFlash);
  });

  test("data without flash gets flash added as observable defaulting to false", () => {
    const vm = makeViewModel();
    const data = { turnoff: makeObservable(false) };
    const result = vm.statusDetails(data);
    expect(typeof result.flash).toBe("function");
    expect(result.flash()).toBe(false);
  });
});

// ===========================================================================
// statusDetails — ct field
// ===========================================================================

describe("statusDetails ct", () => {
  test("data=false returns ct observable defaulting to 0", () => {
    const vm = makeViewModel();
    const result = vm.statusDetails(false);
    expect(typeof result.ct).toBe("function");
    expect(result.ct()).toBe(0);
  });

  test("data with existing ct observable is left unchanged", () => {
    const vm = makeViewModel();
    const existingCt = makeObservable(370);
    const data = { turnoff: makeObservable(false), flash: makeObservable(false), ct: existingCt };
    const result = vm.statusDetails(data);
    expect(result.ct).toBe(existingCt);
  });

  test("data without ct gets ct added as observable defaulting to 0", () => {
    const vm = makeViewModel();
    const data = { turnoff: makeObservable(false), flash: makeObservable(false) };
    const result = vm.statusDetails(data);
    expect(typeof result.ct).toBe("function");
    expect(result.ct()).toBe(0);
  });
});

// ===========================================================================
// onBeforeBinding — flash normalisation
// ===========================================================================

describe("onBeforeBinding flash normalisation", () => {
  test("items already having flash as an observable are left unchanged", () => {
    const existingFlash = makeObservable(true);
    const item = { event: makeObservable("PrintDone"), flash: existingFlash };
    const vm = makeViewModel({ statusDict: makeStatusDictMock([item]) });
    // onBeforeBinding was already called by makeViewModel; call again to verify
    // idempotency — the original observable must not be replaced
    vm.onBeforeBinding();
    expect(item.flash).toBe(existingFlash);
  });

  test("items without flash get flash added as observable defaulting to false", () => {
    const item = { event: makeObservable("PrintDone") }; // no flash key
    makeViewModel({ statusDict: makeStatusDictMock([item]) });
    expect(typeof item.flash).toBe("function");
    expect(item.flash()).toBe(false);
  });

  test("items with plain boolean flash get it wrapped in an observable", () => {
    const item = { event: makeObservable("PrintDone"), flash: false };
    makeViewModel({ statusDict: makeStatusDictMock([item]) });
    expect(typeof item.flash).toBe("function");
    expect(item.flash()).toBe(false);
  });
});

// ===========================================================================
// onBeforeBinding — ct normalisation
// ===========================================================================

describe("onBeforeBinding ct normalisation", () => {
  test("items already having ct as an observable are left unchanged", () => {
    const existingCt = makeObservable(370);
    const item = { event: makeObservable("PrintDone"), flash: makeObservable(false), ct: existingCt };
    const vm = makeViewModel({ statusDict: makeStatusDictMock([item]) });
    vm.onBeforeBinding();
    expect(item.ct).toBe(existingCt);
  });

  test("items without ct get ct added as observable defaulting to 0", () => {
    const item = { event: makeObservable("PrintDone"), flash: makeObservable(false) };
    makeViewModel({ statusDict: makeStatusDictMock([item]) });
    expect(typeof item.ct).toBe("function");
    expect(item.ct()).toBe(0);
  });

  test("items with plain numeric ct get it wrapped in an observable", () => {
    const item = { event: makeObservable("PrintDone"), flash: makeObservable(false), ct: 300 };
    makeViewModel({ statusDict: makeStatusDictMock([item]) });
    expect(typeof item.ct).toBe("function");
    expect(item.ct()).toBe(300);
  });
});

// ===========================================================================
// toggleCtMode
// ===========================================================================

describe("toggleCtMode", () => {
  test("when ct is 0, sets ct to 370 (warm white default)", () => {
    const vm = makeViewModel();
    const status = { ct: makeObservable(0) };
    vm.toggleCtMode(status);
    expect(status.ct()).toBe(370);
  });

  test("when ct is non-zero, resets ct to 0 (RGB mode)", () => {
    const vm = makeViewModel();
    const status = { ct: makeObservable(370) };
    vm.toggleCtMode(status);
    expect(status.ct()).toBe(0);
  });
});
