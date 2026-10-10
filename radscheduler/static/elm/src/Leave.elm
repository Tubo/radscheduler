module Leave exposing
    ( LeaveState(..)
    , leaveChipClass
    , leaveChipContent
    , leaveIcon
    , leaveState
    , leaveStateClass
    , leaveStateName
    , leaveStateSentence
    , portionLabel
    )

{-| Where a day of leave stands between the senior registrar's and the Director of Training's decisions, and
the chip that shows it.
-}

import Choice exposing (Choice)
import Html exposing (Html, i, text)
import Html.Attributes exposing (attribute, class)
import OpenApi.Common exposing (Nullable(..))
import Radscheduler.Types as T


type LeaveState
    = Cancelled
    | Declined
    | Approved
    | PartlyApproved
    | Pending


leaveState : T.LeaveOut -> LeaveState
leaveState leave =
    let
        reg =
            nullable leave.reg_approved

        dot =
            nullable leave.dot_approved
    in
    if leave.cancelled then
        Cancelled

    else if reg == Just False || dot == Just False then
        Declined

    else if reg == Just True && dot == Just True then
        Approved

    else if reg == Just True || dot == Just True then
        PartlyApproved

    else
        Pending


leaveStateClass : LeaveState -> String
leaveStateClass state =
    case state of
        Cancelled ->
            "cancelled"

        Declined ->
            "declined"

        Approved ->
            "approved"

        PartlyApproved ->
            "partial"

        Pending ->
            "pending"


leaveIcon : LeaveState -> String
leaveIcon state =
    case state of
        Cancelled ->
            "bi-slash-circle"

        Declined ->
            "bi-x-lg"

        Approved ->
            "bi-check-lg"

        PartlyApproved ->
            "bi-hourglass-split"

        Pending ->
            "bi-question-lg"


leaveStateName : LeaveState -> String
leaveStateName state =
    case state of
        Cancelled ->
            "cancelled"

        Declined ->
            "declined"

        Approved ->
            "approved"

        PartlyApproved ->
            "approved by one, waiting on the other"

        Pending ->
            "waiting for approval"


{-| Names who has decided and who is still to: "Senior registrar approved · waiting on the Director of Training."
-}
leaveStateSentence : T.LeaveOut -> String
leaveStateSentence leave =
    let
        reg =
            nullable leave.reg_approved

        dot =
            nullable leave.dot_approved
    in
    if leave.cancelled then
        "Cancelled."

    else
        case ( reg, dot ) of
            ( Just True, Just True ) ->
                "Approved by the senior registrar and the Director of Training."

            ( Just False, _ ) ->
                "Declined by the senior registrar."

            ( _, Just False ) ->
                "Declined by the Director of Training."

            ( Just True, Nothing ) ->
                "Senior registrar approved · waiting on the Director of Training."

            ( Nothing, Just True ) ->
                "Director of Training approved · waiting on the senior registrar."

            ( Nothing, Nothing ) ->
                "Waiting on the senior registrar and the Director of Training."


portionLabel : T.LeaveOut -> String
portionLabel leave =
    case leave.portion of
        "AM" ->
            " (morning)"

        "PM" ->
            " (afternoon)"

        _ ->
            " (all day)"


{-| A leave chip's classes: its state, and for a half day the half it shades.
-}
leaveChipClass : LeaveState -> T.LeaveOut -> String
leaveChipClass state leave =
    "re-chip re-leave is-"
        ++ leaveStateClass state
        ++ (case leave.portion of
                "AM" ->
                    " is-am"

                "PM" ->
                    " is-pm"

                _ ->
                    ""
           )


{-| The state icon and the type, followed by the half ("AL·pm") for a half day.
-}
leaveChipContent : Choice -> LeaveState -> T.LeaveOut -> List (Html msg)
leaveChipContent choice state leave =
    [ i [ class ("bi " ++ leaveIcon state), attribute "aria-hidden" "true" ] []
    , text choice.short
    , if leave.portion == "ALL" then
        text ""

      else
        text ("·" ++ String.toLower leave.portion)
    ]


nullable : Nullable a -> Maybe a
nullable value =
    case value of
        Present a ->
            Just a

        Null ->
            Nothing
