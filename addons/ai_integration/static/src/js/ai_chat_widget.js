odoo.define('ai_integration.chat_widget', function (require) {
'use strict';

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var ajax = require('web.ajax');
var session = require('web.session');
var QWeb = core.qweb;
var _t = core._t;

/**
 * AI Chat Widget - Client Action
 * Hiển thị giao diện chat với AI Assistant
 */
var AIChatWidget = AbstractAction.extend({
    hasControlPanel: false,
    contentTemplate: 'ai_integration.ChatFullPage',
    
    events: {
        'click .ai-chat-send': '_onSendMessage',
        'keypress .ai-chat-input': '_onInputKeypress',
        'click .ai-quick-action': '_onQuickAction',
        'click .ai-clear-chat': '_onClearChat',
        'click .ai-new-session': '_onNewSession',
        'click .ai-toggle-history': '_onToggleHistory',
        'click .ai-close-sidebar': '_onToggleHistory',
        'click .ai-history-item': '_onLoadHistory',
        'click .ai-delete-history': '_onDeleteHistory',
    },

    /**
     * @override
     */
    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.action = action;
        this.sessionId = null;
        this.messages = [];
        this.isLoading = false;
        this.module = action.context && action.context.default_module;
        this.activeModel = action.context && action.context.active_model;
        this.activeResId = action.context && action.context.active_id;
        this.chatHistory = [];
        this.showHistory = false;
    },

    /**
     * @override
     */
    willStart: function () {
        var self = this;
        return this._super.apply(this, arguments);
    },

    /**
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._initChat();
            self._loadChatHistory();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Khởi tạo chat session
     * @private
     * @param {boolean} forceNew - Force create new session
     */
    _initChat: function (forceNew) {
        var self = this;
        
        // If forcing new session, create a new one
        if (forceNew) {
            return this._rpc({
                model: 'ai.chat.session',
                method: 'create',
                args: [{
                    user_id: session.uid,
                    active_model: this.activeModel,
                    active_res_id: this.activeResId,
                    module: this.module,
                }],
            }).then(function (sessionId) {
                self.sessionId = sessionId;
                self.messages = [];
                self._renderMessages();
                self._focusInput();
                self._loadChatHistory();
                return sessionId;
            });
        }
        
        // Create or get existing session
        return this._rpc({
            model: 'ai.chat.session',
            method: 'create_or_get_session',
            args: [{
                module: this.module,
                active_model: this.activeModel,
                active_res_id: this.activeResId,
            }],
        }).then(function (session) {
            self.sessionId = session.id;
            self.messages = session.messages || [];
            self._renderMessages();
            self._focusInput();
        });
    },

    /**
     * Gửi tin nhắn đến AI
     * @private
     * @param {string} message
     */
    _sendMessage: function (message) {
        var self = this;
        
        if (!message || !message.trim()) {
            return Promise.resolve();
        }

        // Add user message to UI
        this._addMessage({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString(),
        });

        this.isLoading = true;
        this._setLoading(true);

        return this._rpc({
            model: 'ai.chat.orchestrator',
            method: 'send_message',
            args: [this.sessionId, message, {
                active_model: this.activeModel,
                active_res_id: this.activeResId,
                module: this.module,
            }],
        }).then(function (response) {
            self.isLoading = false;
            self._setLoading(false);

            if (response.success) {
                self._addMessage({
                    role: 'assistant',
                    content: response.message || response.data || 'Không có phản hồi',
                    timestamp: new Date().toISOString(),
                });
            } else {
                self._showError(response.error || 'Có lỗi xảy ra');
            }
        }).catch(function (error) {
            self.isLoading = false;
            self._setLoading(false);
            self._showError('Lỗi kết nối: ' + (error.message || error.data || error));
        });
    },

    /**
     * Thêm tin nhắn vào UI
     * @private
     * @param {Object} message
     */
    _addMessage: function (message) {
        // Normalize timestamp field
        if (!message.timestamp && message.create_date) {
            message.timestamp = message.create_date;
        }
        this.messages.push(message);
        this._renderMessages();
        this._scrollToBottom();
    },

    /**
     * Render lại danh sách tin nhắn
     * @private
     */
    _renderMessages: function () {
        var self = this;
        var $messagesContainer = this.$('.ai-chat-messages');
        if (!$messagesContainer.length) {
            return;
        }

        $messagesContainer.empty();

        // Group messages into Q&A pairs
        var conversations = [];
        var currentConversation = null;
        
        this.messages.forEach(function (msg) {
            if (msg.role === 'user') {
                // Start new conversation with user question
                currentConversation = {
                    question: msg,
                    answer: null
                };
                conversations.push(currentConversation);
            } else if (msg.role === 'assistant' && currentConversation) {
                // Add assistant answer to current conversation
                currentConversation.answer = msg;
            }
        });

        // Render each conversation as a card with Q&A sections
        conversations.forEach(function (conv) {
            var $card = $('<div>').addClass('ai-conversation-card');
            
            // Question section
            var $questionSection = $('<div>').addClass('ai-question-section');
            var $questionHeader = $('<div>').addClass('ai-section-header')
                .append($('<i>').addClass('fa fa-user-circle'))
                .append($('<span>').text('Câu hỏi của bạn'));
            var $questionContent = $('<div>').addClass('ai-section-content')
                .html(self._formatMessage(conv.question.content));
            var $questionTime = $('<div>').addClass('ai-section-time')
                .text(self._formatTime(conv.question.timestamp));
            
            $questionSection.append($questionHeader, $questionContent, $questionTime);
            
            // Answer section (if exists)
            if (conv.answer) {
                var $answerSection = $('<div>').addClass('ai-answer-section');
                var $answerHeader = $('<div>').addClass('ai-section-header')
                    .append($('<i>').addClass('fa fa-robot'))
                    .append($('<span>').text('Trả lời của AI'));
                var $answerContent = $('<div>').addClass('ai-section-content')
                    .html(self._formatMessage(conv.answer.content));
                var $answerTime = $('<div>').addClass('ai-section-time')
                    .text(self._formatTime(conv.answer.timestamp));
                
                $answerSection.append($answerHeader, $answerContent, $answerTime);
                $card.append($questionSection, $answerSection);
            } else {
                $card.append($questionSection);
            }
            
            $messagesContainer.append($card);
        });
        
        self._scrollToBottom();
    },

    /**
     * Format nội dung tin nhắn (markdown -> HTML)
     * @private
     * @param {string} content
     * @returns {string}
     */
    _formatMessage: function (content) {
        if (!content) return '';
        
        // Simple markdown formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br/>');
    },

    /**
     * Format timestamp
     * @private
     * @param {string} timestamp
     * @returns {string}
     */
    _formatTime: function (timestamp) {
        if (!timestamp) return '';
        var date = new Date(timestamp);
        return date.toLocaleTimeString('vi-VN', { 
            hour: '2-digit', 
            minute: '2-digit',
            timeZone: 'Asia/Ho_Chi_Minh'
        });
    },

    /**
     * Scroll xuống cuối danh sách tin nhắn
     * @private
     */
    _scrollToBottom: function () {
        var $container = this.$('.ai-chat-messages');
        if ($container.length) {
            $container.scrollTop($container[0].scrollHeight);
        }
    },

    /**
     * Focus vào input
     * @private
     */
    _focusInput: function () {
        this.$('.ai-chat-input').focus();
    },

    /**
     * Hiển thị/ẩn loading
     * @private
     * @param {boolean} loading
     */
    _setLoading: function (loading) {
        this.$('.ai-chat-send').prop('disabled', loading);
        this.$('.ai-chat-input').prop('disabled', loading);
        
        if (loading) {
            this.$('.ai-chat-loading').show();
        } else {
            this.$('.ai-chat-loading').hide();
        }
    },

    /**
     * Hiển thị lỗi
     * @private
     * @param {string} message
     */
    _showError: function (message) {
        this.displayNotification({
            title: _t('Lỗi'),
            message: message,
            type: 'danger',
        });
    },

    /**
     * Xóa lịch sử chat
     * @private
     */
    _clearChat: function () {
        var self = this;
        
        return this._rpc({
            model: 'ai.chat.session',
            method: 'clear_session',
            args: [this.sessionId],
        }).then(function () {
            self.messages = [];
            self._renderMessages();
            self._loadChatHistory();
            self.displayNotification({
                title: _t('Thành công'),
                message: _t('Đã xóa lịch sử chat'),
                type: 'success',
            });
        });
    },

    /**
     * Load chat history list
     * @private
     */
    _loadChatHistory: function () {
        var self = this;
        
        return this._rpc({
            model: 'ai.chat.session',
            method: 'search_read',
            domain: [['create_uid', '=', session.uid]],
            fields: ['id', 'name', 'create_date', 'message_count'],
            limit: 20,
            order: 'create_date DESC',
        }).then(function (sessions) {
            self.chatHistory = sessions;
            self._renderHistory();
        });
    },

    /**
     * Render chat history sidebar
     * @private
     */
    _renderHistory: function () {
        var self = this;
        var $historyList = this.$('.ai-history-list');
        if (!$historyList.length) {
            return;
        }

        $historyList.empty();

        if (this.chatHistory.length === 0) {
            $historyList.append(
                $('<div>').addClass('ai-history-empty')
                    .html('<i class="fa fa-history"></i><p>Chưa có lịch sử chat</p>')
            );
            return;
        }

        this.chatHistory.forEach(function (session) {
            var date = new Date(session.create_date);
            var dateStr = date.toLocaleDateString('vi-VN', { 
                day: '2-digit', 
                month: '2-digit',
                year: 'numeric',
                timeZone: 'Asia/Ho_Chi_Minh'
            });
            var timeStr = date.toLocaleTimeString('vi-VN', { 
                hour: '2-digit', 
                minute: '2-digit',
                timeZone: 'Asia/Ho_Chi_Minh'
            });
            
            var $item = $('<div>').addClass('ai-history-item')
                .attr('data-session-id', session.id)
                .toggleClass('active', session.id === self.sessionId);
            
            var $content = $('<div>').addClass('ai-history-item-content');
            $content.append(
                $('<div>').addClass('ai-history-item-title').text(session.name || 'Chat ' + session.id)
            );
            $content.append(
                $('<div>').addClass('ai-history-item-meta')
                    .append($('<span>').addClass('ai-history-date').html('<i class="fa fa-calendar"></i> ' + dateStr))
                    .append($('<span>').addClass('ai-history-time').html('<i class="fa fa-clock-o"></i> ' + timeStr))
            );
            $content.append(
                $('<div>').addClass('ai-history-item-count')
                    .html('<i class="fa fa-comments"></i> ' + (session.message_count || 0) + ' tin nhắn')
            );
            
            var $deleteBtn = $('<button>').addClass('ai-delete-history btn btn-sm')
                .attr('data-session-id', session.id)
                .html('<i class="fa fa-trash"></i>')
                .attr('title', 'Xóa lịch sử');
            
            $item.append($content).append($deleteBtn);
            $historyList.append($item);
        });
    },

    /**
     * Toggle history sidebar
     * @private
     */
    _toggleHistory: function () {
        this.showHistory = !this.showHistory;
        this.$('.ai-chat-sidebar').toggleClass('open', this.showHistory);
        this.$('.ai-toggle-history').toggleClass('active', this.showHistory);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onSendMessage: function (ev) {
        ev.preventDefault();
        var $input = this.$('.ai-chat-input');
        var message = $input.val().trim();
        
        if (message) {
            this._sendMessage(message);
            $input.val('');
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onInputKeypress: function (ev) {
        if (ev.which === 13 && !ev.shiftKey) {
            ev.preventDefault();
            this._onSendMessage(ev);
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onQuickAction: function (ev) {
        ev.preventDefault();
        var message = $(ev.currentTarget).data('prompt');
        if (message) {
            this.$('.ai-chat-input').val(message);
            this._onSendMessage(ev);
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onClearChat: function (ev) {
        ev.preventDefault();
        var self = this;
        
        if (confirm(_t('Bạn có chắc muốn xóa toàn bộ lịch sử chat?'))) {
            self._clearChat();
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onNewSession: function (ev) {
        ev.preventDefault();
        var self = this;
        
        // Force create new session
        self.sessionId = null;
        self.messages = [];
        self._renderMessages();
        
        // Create new session (forceNew = true)
        self._initChat(true).then(function () {
            self.displayNotification({
                title: _t('Thành công'),
                message: _t('Đã tạo phiên chat mới'),
                type: 'success',
            });
        });
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onToggleHistory: function (ev) {
        ev.preventDefault();
        this._toggleHistory();
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onLoadHistory: function (ev) {
        ev.preventDefault();
        var $item = $(ev.currentTarget);
        var sessionId = parseInt($item.data('session-id'));
        var self = this;
        
        if (sessionId === this.sessionId) {
            return;
        }
        
        // Load session and its messages
        this._rpc({
            model: 'ai.chat.message',
            method: 'search_read',
            domain: [['session_id', '=', sessionId]],
            fields: ['role', 'content', 'create_date'],
            order: 'id asc',
        }).then(function (messages) {
            self.sessionId = sessionId;
            self.messages = messages.map(function(msg) {
                return {
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.create_date,
                };
            });
            self._renderMessages();
            self._renderHistory();
            
            // Close sidebar on mobile
            if (self.showHistory) {
                self._toggleHistory();
            }
            
            self.displayNotification({
                title: _t('Thành công'),
                message: _t('Đã tải lịch sử chat'),
                type: 'info',
            });
        });
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onDeleteHistory: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var $btn = $(ev.currentTarget);
        var sessionId = parseInt($btn.data('session-id'));
        var self = this;
        
        if (!confirm(_t('Bạn có chắc muốn xóa lịch sử chat này?'))) {
            return;
        }
        
        this._rpc({
            model: 'ai.chat.session',
            method: 'unlink',
            args: [[sessionId]],
        }).then(function () {
            if (sessionId === self.sessionId) {
                self.sessionId = null;
                self.messages = [];
                self._renderMessages();
                self._initChat();
            }
            self._loadChatHistory();
            self.displayNotification({
                title: _t('Thành công'),
                message: _t('Đã xóa lịch sử chat'),
                type: 'success',
            });
        });
    },
});

core.action_registry.add('ai_chat_widget', AIChatWidget);

return AIChatWidget;

});

