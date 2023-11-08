export const contentsDelete = (e) => {
	e.prevent.default();
	// console.log('hi', e);
}

export const getValue = (id) => {
	const getId = id;
	const getElement = document.getElementById(getId);
	const getValue = getElement.value;

	const initialize = () => {
		getElement.value = '';
	}

	initialize();

	return getValue;
};