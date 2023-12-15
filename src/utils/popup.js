import { isThisString } from "./detectDataType";
import { findAfterWordByRegEx } from "./withRegExDoFindWord";
import { simpleToggleClass } from "./toggleClasses";

// 윈도우 팝업
const winPop = {
	url: '',
	target: '',
	features: '',
};

const rewriteString = ( str, position ) => {

	const widthRegex = /width=(\d+)/;
	const heightRegex = /height=(\d+)/;
	const leftRegex = /left=(\d+)/;
	const topRegex = /top=(\d+)/;

	const reg = {};
	const result = {};
	
	reg.widthVal = findAfterWordByRegEx(str, widthRegex);
	reg.heightVal = findAfterWordByRegEx(str, heightRegex);
	reg.leftVal = findAfterWordByRegEx(str, leftRegex);
	reg.topVal = findAfterWordByRegEx(str, topRegex);

	const defaultWidth = 700;
	const defaultHeight = 550;
	console.log('ffff', reg);
	result.widthString = (reg.widthVal ? `width=${reg.widthVal}, ` : `width=${defaultWidth}px, `);
	result.heightString = (reg.heightVal ? `height=${reg.heightVal}, ` : `height=${defaultHeight}px, `);

	result.leftString = (reg.leftVal ? `left=${reg.leftVal}, ` : '');
	result.topString = (reg.topVal ? `top=${reg.topVal}, ` : '');

	if (position === 'center') {

		const _width = document.body.clientWidth;
		const _height = ((window.outerHeight < window.screen.availHeight) ? window.outerHeight : window.screen.availHeight);
		const _locationX = (!((window.screenX || window.screenLeft) < 0) ? (window.screenX || window.screenLeft) : 0);
		
		const horizontal = (reg.widthVal ? (_locationX + ((_width / 2) - (reg.widthVal / 2))) : (_locationX + ((_width / 2) - (reg.widthVal / 2))));
		const vertical = (reg.heightVal ? ((_height / 2) - (reg.heightVal / 2)) : ((defaultHeight / 2) - (reg.heightVal / 2)));

		result.leftString = (reg.leftVal ? `left=${horizontal}` : '');
		result.topString = (reg.topVal ? `top=${vertical}` : '');

		return result;
	};

	return result;

};

const setWindowFeatures = ( str, position ) => {
	const result = rewriteString(str, position);
	return `${result.widthString} ${result.heightString} ${result.leftString} ${result.topString} noopener noreferrer`;
};

const popped = ( url, target, windowFeatures ) => {
	window.open(url, target, windowFeatures);
	return;
};

export const getPopupPageInfo = ( parameters ) => {
	winPop.url = isThisString(parameters.url) || '/error';
	winPop.target = isThisString(parameters.target) || '_blank';
	winPop.features = setWindowFeatures(parameters.features, parameters.location) || '';
	
	return;
};

// submit function 받을 준비
export const windowPopup = ( func ) => {
	popped(winPop.url, winPop.target, winPop.features);
};


// 모달 팝업
const modal = {
	elements: '',
	cssName: '',
	message: '',
	buttonText: '',
};

export const getPopupElementsAndCustomCssName = ( cssClass ) => {
	return modal.cssName = cssClass;
};

export const getPopupCoreMessage = ( html ) => {
	return modal.message = html;
};

const setMessage = ( ingredients ) => {
	const messageWrapper = (ingredients.elements.children[0].classList.contains('modal-body')) ? ingredients.elements.children[0] : ingredients.elements;

	if (messageWrapper.classList.contains('modal-core') === true) {
		messageWrapper.innerHTML = ingredients.message;
	} else if (messageWrapper.children[0].classList.contains('modal-core') === true) {
		messageWrapper.children[0].innerHTML = ingredients.message;
	}
};

const createModalExitButton = ( parent, toggleClassName, text, modalSubmit ) => {
	let upbringing = null;
	const standard = parent;

	if (parent.children[0].classList.contains('modal-body')) {
		upbringing = parent.children[0];
	} else {
		upbringing = parent;
	}

	const modalExitButtonWrap = document.createElement('div');
	modalExitButtonWrap.classList.add('modal-button');
	const MODAL_TOGGLE_CSS_CLASS_NAME = (isThisString(toggleClassName) ? toggleClassName : 'popped');
	const BUTTON_TEXT = (isThisString(text) ? text : '확인');

	const clickEvent = (event) => {
		simpleToggleClass(standard, MODAL_TOGGLE_CSS_CLASS_NAME);
		document.body.removeChild(standard);

		event.target.removeEventListener('click', (event) => clickEvent(event));
	};

	const button = document.createElement('button');
	button.textContent = BUTTON_TEXT;
	button.addEventListener('click', (event) => {
		clickEvent(event);
	});

	upbringing.appendChild(modalExitButtonWrap);
	modalExitButtonWrap.appendChild(button);
	
	return;
};


export const modalPopupAllowClickOuterSpace = ( buttonText ) => {
	const modalBackground = document.createElement('div');
	modalBackground.style.height = (document.body.clientHeight < window.innerHeight) ? `${window.innerHeight}px` : `${document.body.clientHeight}px`;

	const modalBody = document.createElement('div');
	const modalCore = document.createElement('div');

	const MODAL_BACKGROUND_CSS_CLASS_NAME = 'modal-background';
	const MODAL_BODY_CSS_CLASS_NAME = 'modal-body';
	const MODAL_CORE_CSS_CLASS_NAME = 'modal-core';
	const MODAL_TOGGLE_CSS_CLASS_NAME = 'popped';

	const MODAL_BUTTON_TEXT = buttonText || '확인';

	modalBackground.classList.add(MODAL_BACKGROUND_CSS_CLASS_NAME);
	modalBody.classList.add(MODAL_BODY_CSS_CLASS_NAME);
	modalCore.classList.add(MODAL_CORE_CSS_CLASS_NAME);

	const clickEvent = (event) => {
		if (event.target.classList.contains(MODAL_BODY_CSS_CLASS_NAME)) {
			simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);
			document.body.removeChild(modalBackground);
		}
	};

	document.body.appendChild(modalBackground);
	modalBackground.appendChild(modalBody);
	modalBody.appendChild(modalCore);

	simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);

	modalBackground.addEventListener('click', (event) => clickEvent(event));
	
	modal.elements = modalBackground;

	setMessage(modal);

	modalBackground.removeEventListener('click', (event) => clickEvent(event));

	return;
};


// submit function 받을 준비
export const modalPopupDisallowClickOuterSpace = ( func, buttonText ) => {
	const modalBackground = document.createElement('div');
	modalBackground.style.height = (document.body.clientHeight < window.innerHeight) ? `${window.innerHeight}px` : `${document.body.clientHeight}px`;

	const modalBody = document.createElement('div');
	const modalCore = document.createElement('div');

	const MODAL_BACKGROUND_CSS_CLASS_NAME = 'modal-background';
	const MODAL_BODY_CSS_CLASS_NAME = 'modal-body';
	const MODAL_CORE_CSS_CLASS_NAME = 'modal-core';
	const MODAL_TOGGLE_CSS_CLASS_NAME = 'popped';

	const MODAL_BUTTON_TEXT = buttonText || '확인';

	modalBackground.classList.add(MODAL_BACKGROUND_CSS_CLASS_NAME);
	modalBody.classList.add(MODAL_BODY_CSS_CLASS_NAME);
	modalCore.classList.add(MODAL_CORE_CSS_CLASS_NAME);

	document.body.appendChild(modalBackground);
	modalBackground.appendChild(modalBody);
	modalBody.appendChild(modalCore);

	simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);

	if (modalBackground.classList.contains(MODAL_TOGGLE_CSS_CLASS_NAME)) {
		createModalExitButton(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME, MODAL_BUTTON_TEXT);
	}
	
	modal.elements = modalBackground;

	setMessage(modal);

	return;
};