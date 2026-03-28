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
  global.$ = (fn) => { if (typeof fn === "function") fn(); };
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

function makeStatusDictMock() {
  const items = [];
  return {
    push:   jest.fn().mockImplementation((item) => items.push(item)),
    remove: jest.fn().mockImplementation((item) => {
      const idx = items.indexOf(item);
      if (idx !== -1) items.splice(idx, 1);
    }),
    _items: items,
  };
}

function makeViewModel(pluginSettingsOverrides = {}) {
  const statusDict = makeStatusDictMock();
  const pluginSettings = {
    statusDict,
    plugid: makeObservable("2"),
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
    vm.onSettingsShown();
    expect(vm.getbridgestatus).toHaveBeenCalledTimes(1);
  });
});
