// The Web Worker of an interpreter of kongalib.scripting in the browser (Pyodide): started by _WorkerBackend
// from a blob: URL, so nothing has to be served; it gets Pyodide, its packages and the wheels from the URLs
// in the 'init' message, then runs the requests of the host (see plans/scripting_web_worker.md, phase B).
//
// Messages, both ways, are [ kind, id, payload ] with payload a Uint8Array:
//   host -> worker: 'init' (JSON of the configuration), 'control' (pickled run/quit), 'interrupt',
//                   'reply' (to the call with that id)
//   worker -> host: 'control' (pickled bad_connection), 'call' (call or notification of the script),
//                   'ready', 'error' (UTF-8 text)
//
// Control requests run one after the other with callPromising, so the script can suspend its stack
// (pyodide.ffi.run_sync) while it waits for the host; replies and interrupts are delivered at once,
// also while a script is suspended.

let pyodide = null;
let handle = null;
let ready = null;
let chain = Promise.resolve();

function post(kind, id, payload) {
	const bytes = payload ?? new Uint8Array(0);
	self.postMessage([ kind, id, bytes ], [ bytes.buffer ]);
}

function fail(error) {
	post('error', 0, new TextEncoder().encode(String((error && error.stack) || error)));
}

async function init(config) {
	const { loadPyodide } = await import(new URL('pyodide.mjs', config.index_url).href);
	pyodide = await loadPyodide({ indexURL: config.index_url });
	if (config.packages && config.packages.length)
		await pyodide.loadPackage(config.packages, { messageCallback: () => {} });
	const sitePackages = pyodide.runPython("import site; site.getsitepackages()[0]");
	for (const wheel of config.wheels || []) {
		const response = await fetch(wheel);
		if (!response.ok)
			throw new Error(`${wheel}: ${response.status} ${response.statusText}`);
		pyodide.unpackArchive(await response.arrayBuffer(), 'wheel', { extractDir: sitePackages });
	}
	pyodide.runPython("import importlib; importlib.invalidate_caches()");
	const scripting = pyodide.pyimport('kongalib.scripting');
	scripting._worker_setup();
	handle = {
		control: scripting._worker_control,
		message: scripting._worker_message,
	};
	post('ready', 0);
}

self.onmessage = (event) => {
	const [ kind, id, payload ] = event.data;
	if (kind === 'init') {
		ready = init(JSON.parse(new TextDecoder().decode(payload)));
		ready.catch(fail);
		chain = ready;
		return;
	}
	if (kind === 'control') {
		chain = chain.then(() => handle.control.callPromising(payload)).catch(fail);
		return;
	}
	// 'reply', 'interrupt': not behind the running request, which may be waiting for them
	ready.then(() => handle.message(kind, id, payload)).catch(fail);
};
