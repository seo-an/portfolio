import { getPopupElementsAndCustomCssName, getPopupCoreMessage, modalPopupAllowClickOuterSpace, modalPopupDisallowClickOuterSpace } from "../../../utils/popup";

export const ModalExamplePageView = ( props ) => {

	const MODAL_CORE_MESSAGE_CSS_CLASS_NAME = 'delete-guestbook-confirm';
	const MODAL_INNER_MESSAGE = `
		<div>
			<h1>🥕</h1>
			<span>carrot!</span>
		</div>
	`;

	getPopupElementsAndCustomCssName(MODAL_CORE_MESSAGE_CSS_CLASS_NAME);
	getPopupCoreMessage(MODAL_INNER_MESSAGE);

	return (
		<>
			<div>
				<h1>Modal 팝업</h1>
			</div>

			<button onClick={modalPopupAllowClickOuterSpace}>배경 클릭 허용 Modal</button>
      <button onClick={modalPopupDisallowClickOuterSpace}>배경 클릭 비허용 Modal</button>
		</>
	);
};