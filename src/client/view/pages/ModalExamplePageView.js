import { modalPopup } from '../../../utils/popup.js';

export const ModalExamplePageView = ( props ) => {

	const MODAL_CORE_MESSAGE_CSS_CLASS_NAME = 'delete-guestbook-confirm';
	const MODAL_INNER_MESSAGE = `
		<div>
			<h1>🥕</h1>
			<span>carrot!</span>
		</div>
	`;

	// getPopupElementsAndCustomCssName(MODAL_CORE_MESSAGE_CSS_CLASS_NAME);
	// getPopupCoreMessage(MODAL_INNER_MESSAGE);

	const action1 = () => {
		const modalLayer = {
			type: 'modalLayer',
			toggleClassName: MODAL_CORE_MESSAGE_CSS_CLASS_NAME,
			messageHTML: MODAL_INNER_MESSAGE,
		};

		modalPopup(modalLayer);
		return;
	}

	const action2 = () => {
		const modal = {
			type: 'modalWithButton',
			messageHTML: MODAL_INNER_MESSAGE,
		};

		modalPopup(modal);
		return;
	}


	return (
		<>
			<div>
				<h1>Modal 팝업</h1>
			</div>

			<button onClick={action1}>배경 클릭 허용 Modal</button>
      <button onClick={action2}>배경 클릭 비허용 Modal</button>
		</>
	);
};